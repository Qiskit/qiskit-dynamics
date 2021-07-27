from typing import OrderedDict, Dict, List, Union, Any
from abc import ABC, abstractmethod
import numpy as np
from copy import deepcopy
from qiskit.quantum_info.operators.base_operator import BaseOperator

from qiskit_dynamics.dispatch import Array


class DynamicalOperator(ABC):
	"""An class for operators used in defining dynamical simulations."""

	DEFAULT_ALIASES = \
		{
			# Note that both strings must be lower case
			'id': 'i',
			'sx': 'x',
			'sy': 'y',
			'sz': 'z',
		}
	"""Aliases available by default for the two-level qubit operators that are realized in this class."""

	def __init__(self, system_id: Any = '', s_type = '', aliases = None):
		""" Initialization of an operator using (optional) id of the subsystem, type, and aliases.

		Args:
			system_id: A unique identifier of the subsystem (degree of freedom) of the operator,
				or an empty string to defer such an identification.
			s_type: A string name of the type of operator.
			aliases: A dictionary of aliases for operator types, allowing users to expand the
				s_type names used for known operators. If ``None``, the field ``DEFAULT_ALIASES``
				is used.
		"""
		self.system_id = system_id
		self._s_type = ''
		self._s_type_unique = ''
		if aliases is None:
			aliases = self.DEFAULT_ALIASES
		self.aliases = aliases
		# must be assigned first, before setting the property self.s_type, which searches the aliases.

		self.s_type = s_type  # must be assigned after self.aliases, because it searches the aliases.
		self.compound_type = ''
		self.compound_ops = None

	def __deepcopy__(self, memo = None):
		"""Constructs a deep copy of the operator, without duplicating the aliases field."""
		cc = DynamicalOperator(self.system_id, self.s_type, self.aliases)
		cc.compound_type = self.compound_type
		cc.compound_ops = deepcopy(self.compound_ops, memo)
		return cc

	def new_operator(self):
		"""A method that must be implemented by subclasses, to return the correct instance subclass."""
		return DynamicalOperator(aliases = self.aliases)

	@property
	def s_type(self) -> str:
		"""A string defining the operator type. Aliases (multiple names) may be used."""
		return self._s_type

	@property
	def s_type_unique(self) -> str:
		"""A unique string defining the operator type, which all aliases must map to."""
		return self._s_type_unique

	@s_type.setter
	def s_type(self, s_type):
		"""A setter of the operator's type, which searches aliases and sets the unique type as well."""
		self._s_type = s_type
		s_type = self.s_type.lower()  # should be here after assigning _s_type with user's string as is
		self._s_type_unique = self.aliases.get(s_type, s_type)

	def __add__(self, other):
		"""Addition of two DynamicalOperators. Returns a new (compound) DynamicalOperator."""
		if not isinstance(other, DynamicalOperator):
			raise Exception("Both operands in an addition must be instances of a DynamicalOperator.")
		result = self.new_operator()
		result.compound_type = '+'
		result.compound_ops = [self, other]
		return result

	# def __pow__(self, power, modulo=None):
	# 	if type(power) is not int:
	# 		raise Exception("Only integer powers are currently supported for operators.")
	# 	result = DynamicalOperator(aliases = self.aliases)
	# 	result.compound_type = '**'
	# 	result.compound_ops = [self, power]
	# 	return result

	def __sub__(self, other):
		"""Subtraction of two DynamicalOperators. Returns a new (compound) DynamicalOperator."""
		return self.__add__(-other)

	def __mul__(self, other):
		"""Multiplication by a DynamicalOperator or a scalar."""
		result = self.new_operator()
		if isinstance(other, DynamicalOperator):
			result.compound_type = '@'  # Indicates operator * operator for OperatorBuilder
			result.compound_ops = [self, other]
			# For a product of two operators, their order must be preserved
			return result
		else:
			other_type = type(other)
			if other_type is complex or other_type is float or other_type is int:
				result.compound_type = '*'  # Indicates operator * scalar for OperatorBuilder
				result.compound_ops = [self, other]
				# For a product of an operator and a scalar, we can put the operator first always.
				# This is used to simplify OperatorBuilder code below, and must not be changed.
				return result
		raise Exception("The second operand of a multiplication must be a DynamicalOperator class or a scalar.")

	def __rmul__(self, other):
		"""Multiplication of a DynamicalOperator by a scalar."""
		result = self.__mul__(other)
		return result

	def __neg__(self):
		"""Unary negation of a DynamicalOperator."""
		result = self.__rmul__(-1.)
		return result

	def __pos__(self):
		"""Unary plus operator prepending a DynamicalOperator."""
		return self

	def get_operator_matrix(self, s_type_unique, dim: int) -> Any:
		"""Returns a matrix describing a realization of the operator specified in the parameters.

		This function is not declared as static in order to allow subclasses to override the
		implementation. However, fields of the ``self`` object are not being used.
		Args:
			s_type_unique: A unique operator type name to generate.
			dim: The physical dimension of the matrix to generate.
		"""
		# TODO: Replace qubit creation with Qiskit Operator.from_label()
		# TODO: Support the following operators at arbitrary dimensions:
		# 		i x y z sp sm n p q a a_ n n^2 0 1 and initial states as in Qiskit
		if s_type_unique == 'null':
			return np.zeros((dim, dim), complex)
		elif dim == 2:
			if s_type_unique == 'i':
				return np.identity(dim, complex)
			elif s_type_unique == 'x':
				return np.asarray([[0, 1], [1, 0]], complex)
			elif s_type_unique == 'y':
				return np.asarray([[0, -1j], [1j, 0]], complex)
			elif s_type_unique == 'z':
				return np.asarray([[1, 0], [0, -1]], complex)
			elif s_type_unique == 'sp':
				return np.asarray([[0, 1], [0, 0]], complex)
			elif s_type_unique == 'sm':
				return np.asarray([[0, 0], [1, 0]], complex)
			elif s_type_unique == '0':
				return np.asarray([[1, 0], [0, 0]], complex)
			elif s_type_unique == '1':
				return np.asarray([[0, 0], [0, 1]], complex)
		raise Exception(
			f"Operator type {s_type_unique} unknown or unsupported for matrix generation with dimension {dim}.")

	def get_kron_matrix(self, left_matrix: Any, right_matrix: Any):
		"""Returns the matrix Kronecker product of the two arguments.

		This function is not declared as static in order to allow subclasses to override the
		implementation. However, fields of the ``self`` object are not being used.
		Args:
			left_matrix: First matrix.
			right_matrix: Second matrix.

		Returns:
			The Kronecker product of the arguments.
		"""
		return np.kron(left_matrix, right_matrix)  # TODO verify whether ordering matters

	def get_zeros_matrix(self, dim: int):
		return self.get_operator_matrix('null', dim)


class DynamicalOperatorKey:
	"""A container for a unique key identifying an operator and a subsystem."""

	def __init__(self, op: DynamicalOperator):
		self.system_id = op.system_id
		self.s_type_unique = op.s_type_unique

	def __hash__(self):
		return hash((self.system_id, self.s_type_unique))


class OperatorBuilder(ABC):
	"""A class for building trees of DynamicalOperators into matrices, or descriptive dictionaries."""

	def __init__(self):
		self._ids = None
		self._identity_matrices = None
		self._subsystems = None
		self._total_dim = 0
		self._dyn_op = None

	def build_dictionaries(self, operators: Union[DynamicalOperator, List[DynamicalOperator]])\
			-> Union[dict, List[dict]]:
		"""Builds a list of flat descriptive dictionaries from a list of DynamicalOperator trees."""
		results = []
		b_flatten = False  # If operators is one instance return a dict, otherwise a list of dicts
		if type(operators) != list:
			b_flatten = True
			operators = [operators]
		for op in operators:
			results.append(self._build_one_dict(op))
		if b_flatten:
			results = results[0]
		return results

	def _build_one_dict(self, operator: DynamicalOperator) -> dict:
		"""Recursively build a flat dictionary out of a (sub-)tree of DynamicalOperators.

		Args:
			operator: A root of the (sub-)tree to be flattened into a dict.
		Returns:
			The structure of the returned flat dict is as follows: Each key identifies uniquely an
			operator that is a product of opeartors, e.g. "X_0 * Z_0 * Y_2" is the unique operator
			that is the ordered product of 3 operators, X on subsystem 0, Z on subsystem 0, and Y on
			subsystem 2. The value is a multiplicative scalar coefficient for this operator.
			The different entries of the dictionary are understood to be summed over.
		Raises:
			An exception if an unidentified operation was found in the tree.
		"""
		# TODO verify value semantics of dict (object) keys
		if operator.compound_type == '+':  # The sub-tree root is a sum of two operators
			result = {}
			for op in operator.compound_ops:
				op_dict: dict = self._build_one_dict(op)  # Build a dict out of each summand
				# We now iterate over all members in the flattened dict, and add them to the result
				# dict - if the unique key already appears there, the scalars are added.
				for key, val in op_dict.items():
					val_sum = val + result.get(key, complex(0.))
					result[key] = val_sum
		elif operator.compound_type == '@':  # The sub-tree root is a product of two operators
			new_key = []
			new_val = complex(1.)
			for op in operator.compound_ops:
				op_dict = self._build_one_dict(op)
				for key, val in op_dict.items():
					for key_element in key:
						new_key.append(key_element)
						# The key of the product operator will be a concatenation of unique keys,
						# order preserved.
					new_val *= val  # The scalar prefactor will be a product of the scalars.
			result = {tuple(new_key): new_val}
		elif operator.compound_type == '*':  # The sub-tree root is a product of operator * scalar
			# Since this product is commutative, the operator is always first in order,
			# as implemented in DynamicalOperator.__mul__ and  DynamicalOperator.__rmul__
			op = operator.compound_ops[0]
			scalar = operator.compound_ops[1]
			op_dict = self._build_one_dict(op)
			for key, val in op_dict.items():
				op_dict[key] = val * scalar
			result = op_dict
		elif operator.compound_type == '':
			result = {tuple([DynamicalOperatorKey(operator)]): complex(1.)}
		else:
			raise Exception(f"Unknown/unsupported concatenation operator {operator.compound_type}.")
		return result

	def build_matrices(self, operators: Union[DynamicalOperator, Dict, List[DynamicalOperator], List[Dict]],
					   subsystems: OrderedDict, dyn_op: DynamicalOperator = None) -> Any:
		"""Build a (possibly list) of matrices from DynamicalOperator or dictionaries thereof.

		Args:
			operators: A DynamicalOperator, a list of DynamicalOperators, a flattened dictionary
				previously built using ``build_dictionaries``, or a list of such dictionaries.
			subsystems: An ordered dictionary for each subsystem (identified using the system_id
				field of the DynamicalOperator), indicating the matrix dimension to assign for
				it, or 0 to discard it from the built results.
			dyn_op: An instance of a subclass of DynamicalOperator. If None is passed (the default),
				an instance of DynamicalOperator itself is assigned. It allows to use subclasses
				in order to overload the function DynamicOperator.get_operator_matrix() invoked
				for matrix creation.
		Returns:
			A matrix or a list of matrices, of the type as returned by
			DynamicOperator.get_operator_matrix() or the subclass instance passed in argument
			dyn_op.
		Raises:
			An exception if an unidentified operation was found in the tree.
		"""
		# TODO implement "pruning" (removal of subsystems)
		if len(subsystems) == 0:
			return None
		b_flatten = False
		if type(operators) != list:
			b_flatten = True
			operators = [operators]
		dims = subsystems.values()
		self._dyn_op = dyn_op
		if self._dyn_op is None:
			self._dyn_op = DynamicalOperator()
		self._total_dim = 1
		for dim in dims:
			if dim > 0:
				self._total_dim *= dim
		if len(operators) == 0:
			return self._dyn_op.get_zeros_matrix(self._total_dim)
		b_dictionaries = False
		for op in operators:
			# Verify operator types are known and identical
			op_type = type(op)
			if op_type is dict:
				b_dictionaries = True
			elif not isinstance(op, DynamicalOperator):
				raise Exception(f"Unsupported class type in parameter operators: {op_type}.")
			elif b_dictionaries:
				raise Exception("All operators must be of the same type (a dictionary or a DynamicalOperator).")

		self._subsystems = subsystems
		self._ids = []
		for sys_id in subsystems.keys():
			self._ids.append(sys_id)
		self._identity_matrices = []
		if b_dictionaries:
			operators_dict: List[Dict] = operators
		else:
			operators_dict = self.build_dictionaries(operators)
		results = []
		for dim in dims:
			self._identity_matrices.append(self._dyn_op.get_operator_matrix('i', dim))
		for op_dict in operators_dict:
			results.append(self._build_one_matrix(op_dict))
		if b_flatten:
			results = results[0]
		return results

	def _build_one_matrix(self, operator_dict: Dict) -> np.ndarray:
		matrix = self._dyn_op.get_zeros_matrix(self._total_dim)
		for key, val in operator_dict.items():
			sub_matrices = {}
			for key_element in key:
				operator_key: DynamicalOperatorKey = key_element
				dim = self._subsystems.get(operator_key.system_id, None)
				if dim is None:
					raise Exception(
						f"An operator was defined with id = {operator_key.system_id}, "
						"but this id does not appear in the subsystems parameter.")
				new_sub_matrix = self._dyn_op.get_operator_matrix(operator_key.s_type_unique, dim)
				sub_matrix = sub_matrices.get(operator_key.system_id, None)
				if sub_matrix is not None:
					new_sub_matrix = sub_matrix @ new_sub_matrix  # note that order of matrix product matters
				sub_matrices[operator_key.system_id] = new_sub_matrix
			op_matrix = None
			n_subsystems = len(self._ids)
			for i in range(n_subsystems):
				sub_matrix = sub_matrices.get(self._ids[i], self._identity_matrices[i])
				if i == 0:
					op_matrix = sub_matrix
				else:
					op_matrix = self._dyn_op.get_kron_matrix(op_matrix, sub_matrix)
			matrix += val * op_matrix  # TODO verify does not require the Identity?
		return matrix


class Sx(DynamicalOperator):
	def __init__(self, system_id = ''):
		super().__init__(system_id, 'x')


class Sy(DynamicalOperator):
	def __init__(self, system_id = ''):
		super().__init__(system_id, 'y')


class Sz(DynamicalOperator):
	def __init__(self, system_id = ''):
		super().__init__(system_id, 'z')


class Sp(DynamicalOperator):
	def __init__(self, system_id = ''):
		super().__init__(system_id, 'sp')


class Sm(DynamicalOperator):
	def __init__(self, system_id = ''):
		super().__init__(system_id, 'sm')


class Sid(DynamicalOperator):
	def __init__(self, system_id = ''):
		super().__init__(system_id, 'id')
