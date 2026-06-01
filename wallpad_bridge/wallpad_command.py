from dataclasses import dataclass
from threading import Lock

from wallpad_protocol import LightCommandAck, LightState, build_light_command

LightStates = tuple[LightState | None, ...]


@dataclass(frozen=True)
class CommandSend:
    light_no: int
    state: LightState
    attempt: int
    packet: bytes


@dataclass(frozen=True)
class CommandConfirmed:
    light_no: int
    state: LightState


@dataclass(frozen=True)
class CommandFailed:
    light_no: int
    state: LightState


CommandAction = CommandSend | CommandConfirmed | CommandFailed


@dataclass
class InFlightLightCommand:
    light_no: int
    state: LightState
    packet: bytes
    attempts: int = 0
    frames_since_send: int = 0
    acked: bool = False


class LightCommandScheduler:
    """Decide when to (re)transmit light commands and when they are confirmed.

    The scheduler is intentionally I/O-free: callers feed it observed status and
    ack frames and it returns the actions to perform. Retransmission is driven by
    *acks*, not just by a timer -- a command is only retried when the wallpad did
    not acknowledge it, so the retry budget is spent on genuinely dropped frames
    rather than on commands that simply have not been reflected in status yet.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        status_frames_before_retry: int = 1,
        confirm_timeout_frames: int = 6,
    ) -> None:
        self.max_attempts = max_attempts
        self.status_frames_before_retry = status_frames_before_retry
        self.confirm_timeout_frames = confirm_timeout_frames
        self._desired: dict[int, LightState] = {}
        self._in_flight: dict[int, InFlightLightCommand] = {}
        self._lock = Lock()

    def enqueue(self, light_no: int, state: LightState) -> None:
        with self._lock:
            self._desired[light_no] = state

            command = self._in_flight.get(light_no)
            if command is not None and command.state != state:
                # A newer intent supersedes the in-flight (now stale) command so
                # its late ack/status cannot confirm the outdated state.
                self._in_flight.pop(light_no)

    def requeue_pending_after_disconnect(self) -> None:
        with self._lock:
            # The desired target is kept for the whole lifetime of an in-flight
            # command, so dropping the in-flight entries is enough to make the
            # next status frame re-send a fresh first attempt after reconnect.
            for light_no, command in self._in_flight.items():
                self._desired.setdefault(light_no, command.state)
            self._in_flight.clear()

    def on_status(self, states: LightStates) -> list[CommandAction]:
        """Convenience entry point: confirm against `states` then emit one send.

        The monitor calls ``confirm_from_status`` and ``next_action`` separately
        so it can confirm on every status frame but only inject a command in the
        safe post-status bus gap; this combined helper keeps single-call usage
        (and the unit tests) straightforward.
        """
        actions: list[CommandAction] = list(self.confirm_from_status(states))
        actions.extend(self.next_action(states))
        return actions

    def confirm_from_status(self, states: LightStates) -> list[CommandConfirmed]:
        with self._lock:
            actions: list[CommandConfirmed] = []

            for light_no, command in list(self._in_flight.items()):
                if self._state_matches(states, light_no, command.state):
                    actions.append(CommandConfirmed(light_no, command.state))
                    self._in_flight.pop(light_no)
                    self._desired.pop(light_no, None)

            for light_no, state in list(self._desired.items()):
                if light_no in self._in_flight:
                    continue

                if self._state_matches(states, light_no, state):
                    actions.append(CommandConfirmed(light_no, state))
                    self._desired.pop(light_no, None)

            return actions

    def next_action(self, states: LightStates) -> list[CommandAction]:
        with self._lock:
            send = self._next_new_send(states)
            if send is not None:
                return [send]

            retry = self._next_retry_or_fail()
            if retry is not None:
                return [retry]

            return []

    def on_ack(self, ack: LightCommandAck) -> list[CommandConfirmed]:
        with self._lock:
            command = self._in_flight.get(ack.light_no)
            if command is None:
                return []

            if ack.requested_state != command.state:
                return []

            # The wallpad received our request: stop retransmitting it. If it
            # already reports the new state we confirm now, otherwise we wait for
            # the next status frame (bounded by confirm_timeout_frames).
            command.acked = True

            if ack.current_state != command.state:
                return []

            self._in_flight.pop(ack.light_no)
            self._desired.pop(ack.light_no, None)
            return [CommandConfirmed(ack.light_no, command.state)]

    def _next_retry_or_fail(self) -> CommandSend | CommandFailed | None:
        for light_no, command in list(self._in_flight.items()):
            command.frames_since_send += 1

            if command.acked:
                # Acknowledged but not yet reflected in status: give the wallpad
                # a bounded grace period instead of re-sending a command it has
                # already accepted.
                if command.frames_since_send >= self.confirm_timeout_frames:
                    self._in_flight.pop(light_no)
                    self._desired.pop(light_no, None)
                    return CommandFailed(light_no, command.state)
                continue

            if command.frames_since_send < self.status_frames_before_retry:
                continue

            if command.attempts >= self.max_attempts:
                self._in_flight.pop(light_no)
                self._desired.pop(light_no, None)
                return CommandFailed(light_no, command.state)

            return self._mark_send(command)

        return None

    def _next_new_send(self, states: LightStates) -> CommandSend | None:
        for light_no, state in self._desired.items():
            if light_no in self._in_flight:
                continue

            if self._state_matches(states, light_no, state):
                continue

            command = InFlightLightCommand(
                light_no=light_no,
                state=state,
                packet=build_light_command(light_no, state.name),
            )
            self._in_flight[light_no] = command
            return self._mark_send(command)

        return None

    def _mark_send(self, command: InFlightLightCommand) -> CommandSend:
        command.attempts += 1
        command.frames_since_send = 0
        return CommandSend(
            light_no=command.light_no,
            state=command.state,
            attempt=command.attempts,
            packet=command.packet,
        )

    def _state_matches(
        self,
        states: LightStates,
        light_no: int,
        state: LightState,
    ) -> bool:
        if light_no < 1 or light_no > len(states):
            return False

        return states[light_no - 1] == state
