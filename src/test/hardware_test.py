import unittest
import hardware


class MotherBoard(unittest.TestCase):
    def __int__(self):
        unittest.TestCase.__init__(self)
        self.mother_board = hardware.motherboard.Driver()

    def test_daq_match(self):
        sample_data = ""
        self.mother_board.received_data.put()
        self.assertEqual(True, False)  # add assertion here


if __name__ == '__main__':
    unittest.main()
