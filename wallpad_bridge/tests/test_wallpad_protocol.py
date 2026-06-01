import unittest

from wallpad_protocol import (
    LightCommandAck,
    LightState,
    build_light_command,
    iter_frames,
    parse_light_command_ack,
    parse_status_frame,
)


class WallpadProtocolTest(unittest.TestCase):
    def test_build_light_command_matches_captured_frames(self):
        expected = {
            (1, "ON"): "f70b01190240110100b6ee",
            (1, "OFF"): "f70b01190240110200b5ee",
            (2, "ON"): "f70b01190240120100b5ee",
            (2, "OFF"): "f70b01190240120200b6ee",
            (3, "ON"): "f70b01190240130100b4ee",
            (3, "OFF"): "f70b01190240130200b7ee",
            (4, "ON"): "f70b01190240140100b3ee",
            (4, "OFF"): "f70b01190240140200b0ee",
            (5, "ON"): "f70b01190240150100b2ee",
            (5, "OFF"): "f70b01190240150200b1ee",
            (6, "ON"): "f70b01190240160100b1ee",
            (6, "OFF"): "f70b01190240160200b2ee",
        }

        for args, frame_hex in expected.items():
            with self.subTest(args=args):
                self.assertEqual(build_light_command(*args), bytes.fromhex(frame_hex))

    def test_parse_status_frame_returns_six_light_states(self):
        frame = bytes.fromhex("f710011904401000020101010202a8ee")

        self.assertEqual(
            parse_status_frame(frame),
            (
                LightState.OFF,
                LightState.ON,
                LightState.ON,
                LightState.ON,
                LightState.OFF,
                LightState.OFF,
            ),
        )

    def test_parse_light_command_ack_returns_confirmed_light_state(self):
        frame = bytes.fromhex("f70b01190440120202b2ee")

        self.assertEqual(
            parse_light_command_ack(frame),
            LightCommandAck(
                light_no=2,
                requested_state=LightState.OFF,
                current_state=LightState.OFF,
            ),
        )

    def test_parse_light_command_ack_rejects_bad_checksum(self):
        frame = bytes.fromhex("f70b01190440120202b4ee")

        self.assertIsNone(parse_light_command_ack(frame))

    def test_iter_frames_keeps_partial_frame_in_buffer(self):
        buffer = bytes.fromhex("00f710011904401000020101010202a8ee f70b0119")

        frames, remainder = iter_frames(buffer)

        self.assertEqual(frames, [bytes.fromhex("f710011904401000020101010202a8ee")])
        self.assertEqual(remainder, bytes.fromhex("f70b0119"))

    def test_iter_frames_splits_back_to_back_frames(self):
        status = bytes.fromhex("f710011904401000020101010202a8ee")
        ack = bytes.fromhex("f70b01190440120202b2ee")

        frames, remainder = iter_frames(status + ack)

        self.assertEqual(frames, [status, ack])
        self.assertEqual(remainder, b"")

    def test_iter_frames_does_not_truncate_on_interior_end_byte(self):
        # Length-prefixed framing must read `frame[1]` bytes and ignore an EE
        # (FRAME_END) that appears inside the payload, instead of cutting short.
        synthetic = bytes.fromhex("f706ee001fee")  # F7 len=6 [EE 00] cksum=1f EE
        status = bytes.fromhex("f710011904401000020101010202a8ee")

        frames, remainder = iter_frames(synthetic + status)

        self.assertEqual(frames, [synthetic, status])
        self.assertEqual(remainder, b"")

    def test_iter_frames_resyncs_past_corrupted_frame(self):
        bad_checksum = bytes.fromhex("f710011904401000020101010202a9ee")  # a9 != a8
        good = bytes.fromhex("f710011904401000020101010202a8ee")

        frames, remainder = iter_frames(bad_checksum + good)

        self.assertEqual(frames, [good])
        self.assertEqual(remainder, b"")

    def test_parse_status_frame_rejects_bad_checksum(self):
        frame = bytes.fromhex("f710011904401000020101010202a9ee")

        self.assertIsNone(parse_status_frame(frame))

    def test_parse_status_frame_rejects_wrong_length(self):
        frame = bytes.fromhex("f7100119044010000201010102a8ee")

        self.assertIsNone(parse_status_frame(frame))


if __name__ == "__main__":
    unittest.main()
