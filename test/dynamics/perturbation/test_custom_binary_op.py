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

"""Tests for custom_binary_op.py"""

import numpy as np
from ddt import ddt, data, unpack

from qiskit_dynamics.perturbation.custom_binary_op import (
    _compile_custom_operation_rule,
    _CustomBinaryOp,
    _CustomMatmul,
    _CustomMul,
)

from ..common import QiskitDynamicsTestCase, TestJaxBase


@ddt
class Test_CustomBinaryOp(QiskitDynamicsTestCase):
    """Test _CustomBinaryOp in the cases of matmul and mul."""

    def setUp(self):
        self.mult_rule1 = [
            (np.array([1.0, 2.0, 3.0]), np.array([[0, 2], [1, 1], [2, 0]])),
            (np.array([1.0]), np.array([[0, 2]])),
            (np.array([3.0]), np.array([[1, 1]])),
        ]

        self.mult_rule2 = [(np.array([1.0, 2.0, 3.0]), np.array([[0, 2], [0, 0], [0, 0]]))]

    @unpack
    @data((lambda A, B: A @ B,), (lambda A, B: A * B,))
    def test_rule1(self, binary_op):
        """Test correct evaluation of rule1."""
        rng = np.random.default_rng(9381)
        A = rng.uniform(size=(3, 5, 5))
        B = rng.uniform(size=(3, 5, 5))

        prod02 = binary_op(A[0], B[2])
        prod11 = binary_op(A[1], B[1])
        prod20 = binary_op(A[2], B[0])
        expected = np.array([prod02 + 2 * prod11 + 3 * prod20, prod02, 3 * prod11])

        custom_op = _CustomBinaryOp(operation_rule=self.mult_rule1, binary_op=binary_op)
        output = custom_op(A, B)

        self.assertAllClose(expected, output)

    @unpack
    @data((lambda A, B: A @ B,), (lambda A, B: A * B,))
    def test_rule2(self, binary_op):
        """Test correct evaluation of rule 2."""
        rng = np.random.default_rng(9381)
        A = rng.uniform(size=(1, 10, 10))
        B = rng.uniform(size=(3, 10, 10))

        prod02 = binary_op(A[0], B[2])
        prod00 = binary_op(A[0], B[0])
        expected = np.array([prod02 + 5 * prod00])

        custom_op = _CustomBinaryOp(operation_rule=self.mult_rule2, binary_op=binary_op)
        output = custom_op(A, B)

        self.assertAllClose(expected, output)

    @unpack
    @data((lambda A, B: A @ B,), (lambda A, B: A * B,))
    def test_vectorized_dot(self, binary_op):
        """Test works for lists of matrices as well."""

        rng = np.random.default_rng(21319)
        A = rng.uniform(size=(3, 4, 5, 5))
        B = rng.uniform(size=(3, 4, 5, 5))

        prod02 = binary_op(A[0], B[2])
        prod11 = binary_op(A[1], B[1])
        prod20 = binary_op(A[2], B[0])
        expected = np.array([prod02 + 2 * prod11 + 3 * prod20, prod02, 3 * prod11])

        custom_op = _CustomBinaryOp(operation_rule=self.mult_rule1, binary_op=binary_op)
        output = custom_op(A, B)

        self.assertAllClose(expected, output)

    def test_matmul_unequal_shapes(self):
        """Test custom matmul with uneven shapes."""
        binary_op = lambda A, B: A @ B

        rng = np.random.default_rng(21319)
        A = rng.uniform(size=(3, 2, 5))
        B = rng.uniform(size=(3, 5, 3))

        prod02 = binary_op(A[0], B[2])
        prod11 = binary_op(A[1], B[1])
        prod20 = binary_op(A[2], B[0])
        expected = np.array([prod02 + 2 * prod11 + 3 * prod20, prod02, 3 * prod11])

        custom_op = _CustomBinaryOp(operation_rule=self.mult_rule1, binary_op=binary_op)
        output = custom_op(A, B)

        self.assertAllClose(expected, output)

    def test_mul_unequal_shapes(self):
        """Test custom mul with uneven shapes."""
        binary_op = lambda A, B: A * B

        rng = np.random.default_rng(21319)
        A = rng.uniform(size=(3, 2, 5))
        B = rng.uniform(size=(3, 1))

        prod02 = binary_op(A[0], B[2])
        prod11 = binary_op(A[1], B[1])
        prod20 = binary_op(A[2], B[0])
        expected = np.array([prod02 + 2 * prod11 + 3 * prod20, prod02, 3 * prod11])

        custom_op = _CustomBinaryOp(operation_rule=self.mult_rule1, binary_op=binary_op)
        output = custom_op(A, B)

        self.assertAllClose(expected, output)


class Test_CustomBinaryOpJAX(Test_CustomBinaryOp, TestJaxBase):
    """JAX version of Test_CustomBinaryOp."""

    def test_jit_grad_matmul(self):
        """Verify jitting and gradding works through _CustomMatmul."""

        from jax import jit, grad

        def func(A, B):
            custom_matmul = _CustomMatmul(self.mult_rule1)
            return custom_matmul(A, B).real.sum()

        jit_grad_func = jit(grad(func))

        A = np.random.rand(3, 5, 5)
        B = np.random.rand(3, 5, 5)

        jit_grad_func(A, B)

    def test_jit_grad_mul(self):
        """Verify jitting and gradding works through _CustomMul."""

        from jax import jit, grad

        def func(A, B):
            custom_mul = _CustomMul(self.mult_rule1)
            return custom_mul(A, B).real.sum()

        jit_grad_func = jit(grad(func))

        A = np.random.rand(3, 5, 5)
        B = np.random.rand(3, 5, 5)

        jit_grad_func(A, B)


class Test_compile_custom_operation_rule(QiskitDynamicsTestCase):
    """Tests for custom operation rule compilation."""

    def setUp(self):
        operation_rule = [
            (np.array([1.0, 2.0, 3.0]), np.array([[0, 2], [1, 1], [2, 0]])),
            (np.array([1.0]), np.array([[0, 2]])),
            (np.array([3.0]), np.array([[1, 1]])),
        ]

        self.compiled_rule1 = _compile_custom_operation_rule(operation_rule)

        operation_rule = [(np.array([1.0, 2.0, 3.0]), np.array([[0, 2], [0, 0], [0, 0]]))]

        self.compiled_rule2 = _compile_custom_operation_rule(operation_rule)

    def test_unique_mult_pairs(self):
        """Test construction of internal unique multiplication pairs."""

        expected = np.array([[0, 2], [1, 1], [2, 0]], dtype=int)
        self.assertAllClose(expected, self.compiled_rule1[0])

        expected = np.array([[0, 2], [0, 0]], dtype=int)
        self.assertAllClose(expected, self.compiled_rule2[0])

    def test_linear_combo_rule(self):
        """Test internal linear combo rule."""

        expected_coeffs = np.array([[1.0, 2.0, 3.0], [1.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
        expected_indices = np.array([[0, 1, 2], [0, -1, -1], [1, -1, -1]])

        coeffs, indices = self.compiled_rule1[1]
        self.assertAllClose(expected_coeffs, coeffs)
        self.assertAllClose(expected_indices, indices)

        expected_coeffs = np.array([[1.0, 2.0, 3.0]])
        expected_indices = np.array([[0, 1, 1]])

        coeffs, indices = self.compiled_rule2[1]
        self.assertAllClose(expected_coeffs, coeffs)
        self.assertAllClose(expected_indices, indices)

    def test_padding(self):
        """Test padding of compiled rule."""

        operation_rule = [
            (np.array([1.0, 2.0, 3.0]), np.array([[0, 2], [1, 1], [2, 0]])),
            (np.array([1.0]), np.array([[0, 2]])),
            (np.array([3.0]), np.array([[1, 1]])),
        ]

        compiled_rule = _compile_custom_operation_rule(
            operation_rule, unique_evaluation_len=5, linear_combo_len=6
        )

        expected_unique_mults = np.array([[0, 2], [1, 1], [2, 0], [-1, -1], [-1, -1]])
        expected_coeffs = np.array(
            [
                [1.0, 2.0, 3.0, 0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [3.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ]
        )
        expected_unique_mult_indices = np.array(
            [[0, 1, 2, -1, -1, -1], [0, -1, -1, -1, -1, -1], [1, -1, -1, -1, -1, -1]]
        )

        self.assertAllClose(expected_unique_mults, compiled_rule[0])
        self.assertAllClose(expected_coeffs, compiled_rule[1][0])
        self.assertAllClose(expected_unique_mult_indices, compiled_rule[1][1])

    def test_index_offset(self):
        """Test index_offset argument."""
        operation_rule = [
            (np.array([1.0, 2.0, 3.0]), np.array([[0, 2], [1, 1], [2, 0]])),
            (np.array([1.0]), np.array([[0, 2]])),
            (np.array([3.0]), np.array([[1, 1]])),
        ]

        compiled_rule = _compile_custom_operation_rule(operation_rule, index_offset=1)

        expected_unique_mults = np.array([[1, 3], [2, 2], [3, 1]])
        expected_coeffs = np.array([[1.0, 2.0, 3.0], [1.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
        expected_unique_mult_indices = np.array([[0, 1, 2], [0, -1, -1], [1, -1, -1]])
        self.assertAllClose(expected_unique_mults, compiled_rule[0])
        self.assertAllClose(expected_coeffs, compiled_rule[1][0])
        self.assertAllClose(expected_unique_mult_indices, compiled_rule[1][1])
