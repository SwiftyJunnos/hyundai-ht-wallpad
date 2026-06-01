from enum import IntEnum
from typing import NamedTuple


FRAME_START = 0xF7
FRAME_END = 0xEE
STATUS_PREFIX = bytes.fromhex("f710011904401000")
STATUS_FRAME_LEN = 16
ACK_FRAME_LEN = 11

# Every wallpad frame is `F7 <len> ... <checksum> EE`, where the second byte is
# the total frame length (0x0B = 11 for query/command/ack, 0x10 = 16 for status).
# These bounds let iter_frames reject obviously bogus length bytes and resync.
MIN_FRAME_LEN = 5
MAX_FRAME_LEN = 64


class LightState(IntEnum):
    ON = 0x01
    OFF = 0x02


class LightCommandAck(NamedTuple):
    light_no: int
    requested_state: LightState
    current_state: LightState


def checksum(frame_without_checksum: bytes) -> int:
    value = 0
    for byte in frame_without_checksum:
        value ^= byte
    return value


def build_light_command(light_no: int, state: str) -> bytes:
    if light_no < 1 or light_no > 6:
        raise ValueError(f"light_no must be 1..6: {light_no}")

    state_value = LightState[state.upper()]
    frame = bytes(
        [
            FRAME_START,
            0x0B,
            0x01,
            0x19,
            0x02,
            0x40,
            0x10 + light_no,
            state_value,
            0x00,
        ]
    )
    return frame + bytes([checksum(frame), FRAME_END])


def has_valid_checksum(frame: bytes) -> bool:
    if len(frame) < 3:
        return False
    return frame[-1] == FRAME_END and frame[-2] == checksum(frame[:-2])


def parse_light_command_ack(frame: bytes) -> LightCommandAck | None:
    if len(frame) != ACK_FRAME_LEN:
        return None

    if not frame.startswith(bytes.fromhex("f70b01190440")):
        return None

    if not has_valid_checksum(frame):
        return None

    light_no = frame[6] - 0x10
    if light_no < 1 or light_no > 6:
        return None

    try:
        requested_state = LightState(frame[7])
        current_state = LightState(frame[8])
    except ValueError:
        return None

    return LightCommandAck(light_no, requested_state, current_state)


def parse_status_frame(frame: bytes) -> tuple[LightState | None, ...] | None:
    if not frame.startswith(STATUS_PREFIX):
        return None

    if len(frame) != STATUS_FRAME_LEN:
        return None

    if not has_valid_checksum(frame):
        return None

    states = []
    for value in frame[8:14]:
        try:
            states.append(LightState(value))
        except ValueError:
            states.append(None)
    return tuple(states)


def iter_frames(buffer: bytes) -> tuple[list[bytes], bytes]:
    """Split a raw byte stream into validated frames.

    Frames are length-prefixed (`frame[1]` is the total length) and end with
    `EE`, so we never rely on scanning for `EE` alone -- payload/checksum bytes
    that happen to equal `EE` or `F7` no longer truncate a frame. Anything that
    fails the length/terminator/checksum checks is dropped one byte at a time to
    resync, and an incomplete trailing frame is returned as the remainder.
    """
    frames: list[bytes] = []

    while True:
        start = buffer.find(bytes([FRAME_START]))
        if start < 0:
            return frames, b""

        # Drop any leading bytes that precede the next frame start.
        buffer = buffer[start:]

        if len(buffer) < 2:
            # Need at least the start byte and the length byte to proceed.
            return frames, buffer

        length = buffer[1]

        if length < MIN_FRAME_LEN or length > MAX_FRAME_LEN:
            # Bogus length byte: skip this start byte and resync.
            buffer = buffer[1:]
            continue

        if len(buffer) < length:
            # Frame not fully received yet; keep it for the next read.
            return frames, buffer

        frame = buffer[:length]
        if frame[-1] == FRAME_END and has_valid_checksum(frame):
            frames.append(frame)
            buffer = buffer[length:]
        else:
            # Malformed frame: drop the start byte and resync on the next F7.
            buffer = buffer[1:]
