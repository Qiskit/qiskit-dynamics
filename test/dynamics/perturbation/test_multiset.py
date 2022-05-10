# This code is part of Qiskit.
#
# (C) Copyright IBM 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# pylint: disable=invalid-name

"""Tests Multiset."""

from qiskit import QiskitError

from qiskit_dynamics.perturbation import Multiset
from qiskit_dynamics.perturbation.multiset import (
    submultiset_filter,
    clean_multisets,
    get_all_submultisets,
)

from ..common import QiskitDynamicsTestCase


class TestMultiset(QiskitDynamicsTestCase):
    """Tests for Multiset class."""

    def test_empty_multiset(self):
        """Test empty Multiset."""
        empty = Multiset({})
        self.assertTrue(empty.count(2) == 0)

    def test_validation(self):
        """Test that non-integer types, and negative counts, raise errors."""

        with self.assertRaises(QiskitError) as qe:
            Multiset({"a": 1})
        self.assertTrue("must be integers" in str(qe.exception))

        with self.assertRaises(QiskitError) as qe:
            Multiset({0: 1, 1: -1})
        self.assertTrue("non-negative" in str(qe.exception))

    def test_eq(self):
        """Test __eq__."""

        self.assertTrue(Multiset({0: 2, 1: 1}) == Multiset({1: 1, 0: 2}))
        self.assertFalse(Multiset({0: 2, 1: 1}) == Multiset({1: 2}))

    def test_issubmultiset(self):
        """Test issubmultiset method."""
        B = Multiset({0: 2, 1: 1})
        self.assertFalse(Multiset({2: 1}).issubmultiset(B))
        self.assertFalse(Multiset({0: 3}).issubmultiset(B))
        self.assertTrue(Multiset({0: 1}).issubmultiset(B))
        self.assertTrue(Multiset({0: 1, 1: 1}).issubmultiset(B))
        self.assertTrue(Multiset({0: 2}).issubmultiset(B))
        self.assertTrue(B.issubmultiset(B))

    def test_union(self):
        """Test union."""

        ms1 = Multiset({0: 2, 1: 1})
        ms2 = Multiset({0: 2, 2: 1})

        self.assertTrue(ms1.union(ms2) == Multiset({0: 4, 1: 1, 2: 1}))

    def test_difference(self):
        """Test difference method."""
        B = Multiset({0: 2, 1: 1, 2: 2})

        self.assertTrue((B - Multiset({0: 1})) == Multiset({0: 1, 1: 1, 2: 2}))
        self.assertTrue((B - Multiset({0: 3})) == Multiset({1: 1, 2: 2}))
        self.assertTrue((B - Multiset({0: 1, 1: 1, 2: 1})) == Multiset({0: 1, 2: 1}))
        self.assertTrue((B - Multiset({0: 1, 2: 1, 1: 1})) == Multiset({0: 1, 2: 1}))
        self.assertTrue((B - Multiset({3: 1})) == B)

    def test_relabel(self):
        """Test relabel."""
        base_multiset = Multiset({0: 2, 1: 1})

        # relabeling one element to one not in the multiset
        self.assertTrue(Multiset({2: 2, 1: 1}) == base_multiset.relabel({0: 2}))

        # relabeling an element not in the set to another not in the set
        self.assertTrue(Multiset({0: 2, 1: 1}) == base_multiset.relabel({2: 3}))

        # relabeling all elements
        self.assertTrue(Multiset({1: 2, 0: 1}) == base_multiset.relabel({0: 1, 1: 0}))

        # empty relabeling
        self.assertTrue(Multiset({0: 2, 1: 1}) == base_multiset.relabel())

    def test_relabel_validation_errors(self):
        """Test relabeling validation errors."""
        base_multiset = Multiset({0: 2, 1: 1})

        with self.assertRaisesRegex(QiskitError, "must imply"):
            base_multiset.relabel({0: 1})

        with self.assertRaisesRegex(QiskitError, "must imply"):
            base_multiset.relabel({0: 0, 2: 0})

    def test_lt(self):
        """Test less than."""
        self.assertTrue(Multiset({0: 2}) < Multiset({1: 2}))
        self.assertTrue(Multiset({0: 2}) < Multiset({0: 2, 1: 2}))
        self.assertFalse(Multiset({0: 2}) < Multiset({0: 2}))
        self.assertFalse(Multiset({0: 2, 1: 2}) < Multiset({0: 2}))
        self.assertFalse(Multiset({1: 2}) < Multiset({0: 2}))
