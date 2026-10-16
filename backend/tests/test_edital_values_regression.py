import unittest
from edital_values import number


class DocumentaryNumbers(unittest.TestCase):
    def test_brazilian_grouped_counts_keep_their_magnitude(self):
        for literal,expected in [('1.000',1000),('10.000',10000),('1000',1000),('40',40),('0',0)]:
            with self.subTest(literal=literal):self.assertEqual(number(literal,integer=True),expected)

    def test_ambiguous_fractional_or_unsupported_counts_stay_unknown(self):
        for literal in ('1,000','1.5','40,0','1e3','-1','10.001','10001','1.000.000','40 questões',None):
            with self.subTest(literal=literal):self.assertIsNone(number(literal,integer=True))

    def test_weights_do_not_silently_change_locale_or_accept_nonfinite_values(self):
        for literal in ('1.000','1e3','NaN','Infinity','-2','0','1001'):
            with self.subTest(literal=literal):self.assertIsNone(number(literal))
        for literal,expected in [('2',2),('1,5',1.5),('0,125',.125),('1.50',1.5),('1.000,0',1000)]:
            with self.subTest(literal=literal):self.assertEqual(number(literal),expected)
