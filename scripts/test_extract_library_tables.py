#!/usr/bin/env python3
"""Prevent unsupported merged/nested cells from leaking into rectangular tests."""
import unittest
import xml.etree.ElementTree as ET
from extract_library_tables import rectangular_parts


class ExtractionTests(unittest.TestCase):
    def parts(self, rows):
        return rectangular_parts(ET.fromstring('<table>'+rows+'</table>'))

    def test_merged_header_preserves_only_contiguous_body(self):
        parts=self.parts('<tr><th colspan="2">heading</th></tr>'
                         '<tr><td>one two</td><td>A</td></tr>'
                         '<tr><td>three</td><td>B</td></tr>')
        self.assertEqual([(a,b,k) for a,b,_,k in parts],[(1,3,'rectangular-body')])
        self.assertEqual(parts[0][2][0][0]['tokens'],[3,3])

    def test_rowspan_occupancy_excludes_following_rows(self):
        parts=self.parts('<tr><td rowspan="2">X</td><td>Y</td><td>Z</td></tr>'
                         '<tr><td>unsafe</td><td>row</td></tr>'
                         '<tr><td>safe</td><td>one</td></tr>'
                         '<tr><td>safe</td><td>two</td></tr>')
        self.assertEqual([(a,b,k) for a,b,_,k in parts],[(2,4,'rectangular-body')])

    def test_zero_rowspan_blocks_the_rest(self):
        self.assertEqual(self.parts('<tr><td rowspan="0">X</td><td>Y</td></tr>'
                                    '<tr><td>A</td><td>B</td></tr>'
                                    '<tr><td>C</td><td>D</td></tr>'),[])

    def test_nested_table_is_not_flattened_into_outer_cells(self):
        self.assertEqual(self.parts('<tr><td><table><tr><td>A</td><td>B</td></tr>'
                                    '<tr><td>C</td><td>D</td></tr></table></td><td>X</td></tr>'),[])

    def test_whole_rectangular_table_and_inline_adjacency(self):
        parts=self.parts('<tbody><tr><td>ab<em>cd</em>ef</td><td>X</td></tr>'
                         '<tr><td>gh</td><td>Y</td></tr></tbody>')
        self.assertEqual(parts[0][3],'whole')
        self.assertEqual(parts[0][2][0][0]['tokens'],[6])


if __name__=='__main__':
    unittest.main()
