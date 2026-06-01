import unittest

from wallpad_command import CommandConfirmed, CommandFailed, CommandSend, LightCommandScheduler
from wallpad_protocol import LightCommandAck, LightState


OFF_STATES = (
    LightState.OFF,
    LightState.OFF,
    LightState.OFF,
    LightState.OFF,
    LightState.OFF,
    LightState.OFF,
)


class LightCommandSchedulerTest(unittest.TestCase):
    def test_sends_one_queued_command_per_status_frame(self):
        scheduler = LightCommandScheduler()

        scheduler.enqueue(1, LightState.ON)
        scheduler.enqueue(2, LightState.ON)

        self.assertEqual(
            scheduler.on_status(OFF_STATES),
            [
                CommandSend(
                    light_no=1,
                    state=LightState.ON,
                    attempt=1,
                    packet=bytes.fromhex("f70b01190240110100b6ee"),
                )
            ],
        )
        self.assertEqual(
            scheduler.on_status(OFF_STATES),
            [
                CommandSend(
                    light_no=2,
                    state=LightState.ON,
                    attempt=1,
                    packet=bytes.fromhex("f70b01190240120100b5ee"),
                )
            ],
        )

    def test_confirming_one_light_does_not_block_sending_next_light(self):
        scheduler = LightCommandScheduler()

        scheduler.enqueue(1, LightState.ON)
        scheduler.enqueue(2, LightState.ON)
        scheduler.on_status(OFF_STATES)

        self.assertEqual(
            scheduler.on_status(
                (
                    LightState.ON,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                )
            ),
            [
                CommandConfirmed(light_no=1, state=LightState.ON),
                CommandSend(
                    light_no=2,
                    state=LightState.ON,
                    attempt=1,
                    packet=bytes.fromhex("f70b01190240120100b5ee"),
                ),
            ],
        )

    def test_retries_unconfirmed_command_after_status_frame_budget(self):
        scheduler = LightCommandScheduler(status_frames_before_retry=2)

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)

        self.assertEqual(scheduler.on_status(OFF_STATES), [])
        self.assertEqual(
            scheduler.on_status(OFF_STATES),
            [
                CommandSend(
                    light_no=1,
                    state=LightState.ON,
                    attempt=2,
                    packet=bytes.fromhex("f70b01190240110100b6ee"),
                )
            ],
        )

    def test_delayed_confirmation_prevents_retry(self):
        scheduler = LightCommandScheduler(status_frames_before_retry=4)

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)

        self.assertEqual(scheduler.on_status(OFF_STATES), [])
        self.assertEqual(scheduler.on_status(OFF_STATES), [])
        self.assertEqual(
            scheduler.on_status(
                (
                    LightState.ON,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                )
            ),
            [CommandConfirmed(light_no=1, state=LightState.ON)],
        )

    def test_confirms_queued_command_without_sending_when_state_already_matches(self):
        scheduler = LightCommandScheduler()

        scheduler.enqueue(1, LightState.ON)

        self.assertEqual(
            scheduler.on_status(
                (
                    LightState.ON,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                )
            ),
            [CommandConfirmed(light_no=1, state=LightState.ON)],
        )

    def test_confirms_command_when_ack_reaches_requested_state(self):
        scheduler = LightCommandScheduler()

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)

        self.assertEqual(
            scheduler.on_ack(
                LightCommandAck(
                    light_no=1,
                    requested_state=LightState.ON,
                    current_state=LightState.ON,
                )
            ),
            [CommandConfirmed(light_no=1, state=LightState.ON)],
        )

    def test_stops_after_max_attempts(self):
        scheduler = LightCommandScheduler(max_attempts=2, status_frames_before_retry=1)

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)
        scheduler.on_status(OFF_STATES)

        self.assertEqual(
            scheduler.on_status(OFF_STATES),
            [CommandFailed(light_no=1, state=LightState.ON)],
        )

    def test_keeps_only_latest_queued_state_per_light(self):
        scheduler = LightCommandScheduler()

        scheduler.enqueue(1, LightState.ON)
        scheduler.enqueue(1, LightState.OFF)

        self.assertEqual(
            scheduler.on_status(OFF_STATES),
            [CommandConfirmed(light_no=1, state=LightState.OFF)],
        )

    def test_ack_for_request_stops_retransmitting_before_state_reflects(self):
        scheduler = LightCommandScheduler(max_attempts=5, status_frames_before_retry=1)

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)

        # Wallpad acked the request but status has not flipped yet.
        self.assertEqual(
            scheduler.on_ack(
                LightCommandAck(
                    light_no=1,
                    requested_state=LightState.ON,
                    current_state=LightState.OFF,
                )
            ),
            [],
        )

        # No needless resend while we wait for the state to be reflected.
        self.assertEqual(scheduler.on_status(OFF_STATES), [])

        # Once status reflects the change, it is confirmed.
        self.assertEqual(
            scheduler.on_status(
                (
                    LightState.ON,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                )
            ),
            [CommandConfirmed(light_no=1, state=LightState.ON)],
        )

    def test_acked_command_fails_after_confirm_timeout(self):
        scheduler = LightCommandScheduler(
            max_attempts=5,
            status_frames_before_retry=1,
            confirm_timeout_frames=3,
        )

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)
        scheduler.on_ack(
            LightCommandAck(
                light_no=1,
                requested_state=LightState.ON,
                current_state=LightState.OFF,
            )
        )

        self.assertEqual(scheduler.on_status(OFF_STATES), [])
        self.assertEqual(scheduler.on_status(OFF_STATES), [])
        self.assertEqual(
            scheduler.on_status(OFF_STATES),
            [CommandFailed(light_no=1, state=LightState.ON)],
        )

    def test_new_intent_supersedes_in_flight_command(self):
        scheduler = LightCommandScheduler(status_frames_before_retry=1)

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)

        # User toggles back to OFF while the ON command is still in flight.
        scheduler.enqueue(1, LightState.OFF)

        # A late ack for the superseded ON command must not confirm anything.
        self.assertEqual(
            scheduler.on_ack(
                LightCommandAck(
                    light_no=1,
                    requested_state=LightState.ON,
                    current_state=LightState.ON,
                )
            ),
            [],
        )

        # Even though the old ON took effect on the bus, we correct it to OFF.
        self.assertEqual(
            scheduler.on_status(
                (
                    LightState.ON,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                    LightState.OFF,
                )
            ),
            [
                CommandSend(
                    light_no=1,
                    state=LightState.OFF,
                    attempt=1,
                    packet=bytes.fromhex("f70b01190240110200b5ee"),
                )
            ],
        )

    def test_resends_in_flight_command_after_reconnect(self):
        scheduler = LightCommandScheduler(status_frames_before_retry=1)

        scheduler.enqueue(1, LightState.ON)
        scheduler.on_status(OFF_STATES)

        scheduler.requeue_pending_after_disconnect()

        # After reconnect the first status frame re-sends a fresh first attempt.
        self.assertEqual(
            scheduler.on_status(OFF_STATES),
            [
                CommandSend(
                    light_no=1,
                    state=LightState.ON,
                    attempt=1,
                    packet=bytes.fromhex("f70b01190240110100b6ee"),
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
