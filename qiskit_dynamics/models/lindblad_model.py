# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# pylint: disable=invalid-name

"""
Lindblad models module.
"""

from typing import Tuple, Union, List, Optional
import numpy as np
from scipy.sparse.csr import csr_matrix

from qiskit import QiskitError
from qiskit.quantum_info.operators import Operator
from qiskit_dynamics.dispatch import Array
from qiskit_dynamics.type_utils import to_numeric_matrix_type
from qiskit_dynamics.signals import Signal, SignalList
from .generator_model import BaseGeneratorModel, GeneratorModel
from .hamiltonian_model import HamiltonianModel, is_hermitian
from .operator_collections import (
    BaseLindbladOperatorCollection,
    DenseLindbladCollection,
    DenseVectorizedLindbladCollection,
    SparseLindbladCollection,
    SparseVectorizedLindbladCollection,
)
from .rotating_frame import RotatingFrame


class LindbladModel(BaseGeneratorModel):
    r"""A model of a quantum system in terms of the Lindblad master equation.

    The Lindblad master equation models the evolution of a density matrix according to:

    .. math::
        \dot{\rho}(t) = -i[H(t), \rho(t)] + \mathcal{D}(t)(\rho(t)),

    where :math:`\mathcal{D}(t)` is the dissipator portion of the equation,
    given by

    .. math::
        \mathcal{D}(t)(\rho(t)) = \sum_j \gamma_j(t) L_j \rho L_j^\dagger
                                  - \frac{1}{2} \{L_j^\dagger L_j, \rho\},

    with :math:`[\cdot, \cdot]` and :math:`\{\cdot, \cdot\}` the
    matrix commutator and anti-commutator, respectively. In the above:

        - :math:`H(t)` denotes the Hamiltonian,
        - :math:`L_j` denotes the :math:`j^{th}` dissipator, or Lindblad,
          operator, and
        - :math:`\gamma_j(t)` denotes the signal corresponding to the
          :math:`j^{th}` Lindblad operator.

    Instantiating an instance of :class:`~qiskit_dynamics.models.LindbladModel`
    requires specifying the above decomposition:

    .. code-block:: python

        lindblad_model = LindbladModel(hamiltonian_operators,
                                       hamiltonian_signals,
                                       static_hamiltonian,
                                       dissipator_operators,
                                       dissipator_signals)

    where the arguments ``hamiltonian_operators``, ``hamiltonian_signals``, and
    ``static_hamiltonian`` are for the Hamiltonian decomposition as in
    :class:`~qiskit_dynamics.models.HamiltonianModel`,
    and the ``dissipator_operators`` correspond to the :math:`L_j`, and the ``dissipator_signals``
    the :math:`g_j(t)`, which default to the constant ``1.``.
    """

    def __init__(
        self,
        static_hamiltonian: Optional[Union[Array, csr_matrix]] = None,
        hamiltonian_operators: Optional[Union[Array, List[csr_matrix]]] = None,
        hamiltonian_signals: Optional[Union[List[Signal], SignalList]] = None,
        static_dissipators: Optional[Union[Array, csr_matrix]] = None,
        dissipator_operators: Optional[Union[Array, List[csr_matrix]]] = None,
        dissipator_signals: Optional[Union[List[Signal], SignalList]] = None,
        rotating_frame: Optional[Union[Operator, Array, RotatingFrame]] = None,
        evaluation_mode: Optional[str] = "dense",
        validate: bool = True,
    ):
        """Initialize.

        Args:
            static_hamiltonian: Constant term in Hamiltonian.
            hamiltonian_operators: List of operators in Hamiltonian with time-dependent
                                   coefficients.
            hamiltonian_signals: Time-dependent coefficients for hamiltonian_operators.
            static_dissipators: List of dissipators with coefficient 1.
            dissipator_operators: List of dissipator operators with time-dependent coefficients.
            dissipator_signals: Time-dependent coefficients for dissipator_operators.
            rotating_frame: Rotating frame in which calcualtions are to be done.
                            If provided, it is assumed that all operators were
                            already in the frame basis.
            evaluation_mode: Evaluation mode to use. See ``LindbladModel.evaluation_mode``
                             for more details.
            validate: If True check input hamiltonian_operators and static_hamiltonian are
                      Hermitian.

        Raises:
            QiskitError: If model insufficiently or incorrectly specified.
        """

        if (
            static_hamiltonian is None
            and hamiltonian_operators is None
            and static_dissipators is None
            and dissipator_operators is None
        ):
            raise QiskitError(
                self.__class__.__name__
                + """ requires at least one of static_hamiltonian,
                              hamiltonian_operators, static_dissipators, or dissipator_operators
                              to be specified at construction."""
            )

        static_hamiltonian = to_numeric_matrix_type(static_hamiltonian)
        hamiltonian_operators = to_numeric_matrix_type(hamiltonian_operators)
        if validate:
            if (hamiltonian_operators is not None) and (not is_hermitian(hamiltonian_operators)):
                raise QiskitError("""LinbladModel hamiltonian_operators must be Hermitian.""")
            if (static_hamiltonian is not None) and (not is_hermitian(static_hamiltonian)):
                raise QiskitError("""LinbladModel static_hamiltonian must be Hermitian.""")

        self._operator_collection = self.construct_operator_collection(
            evaluation_mode=evaluation_mode,
            static_hamiltonian=static_hamiltonian,
            hamiltonian_operators=hamiltonian_operators,
            static_dissipators=static_dissipators,
            dissipator_operators=dissipator_operators,
        )
        self._evaluation_mode = evaluation_mode
        self.vectorized_operators = "vectorized" in evaluation_mode

        self._rotating_frame = None
        self.rotating_frame = rotating_frame

        self.signals = (hamiltonian_signals, dissipator_signals)

    @classmethod
    def from_hamiltonian(
        cls,
        hamiltonian: HamiltonianModel,
        static_dissipators: Optional[Union[Array, csr_matrix]] = None,
        dissipator_operators: Optional[Union[Array, List[csr_matrix]]] = None,
        dissipator_signals: Optional[Union[List[Signal], SignalList]] = None,
        evaluation_mode: Optional[str] = None,
    ):
        """Construct from a :class:`HamiltonianModel`.

        Args:
            hamiltonian: The :class:`HamiltonianModel`.
            static_dissipators: List of dissipators with coefficient 1.
            dissipator_operators: List of dissipators with time-dependent coefficients.
            dissipator_signals: List time-dependent coefficients for dissipator_operators.
            evaluation_mode: Evaluation mode. See LindbladModel.evaluation_mode
                for more information.

        Returns:
            LindbladModel: Linblad model from parameters.
        """

        if evaluation_mode is None:
            evaluation_mode = hamiltonian.evaluation_mode

        return cls(
            hamiltonian_operators=hamiltonian.get_operators(False),
            hamiltonian_signals=hamiltonian.signals,
            dissipator_operators=dissipator_operators,
            dissipator_signals=dissipator_signals,
            static_hamiltonian=hamiltonian.get_static_operator(False),
            evaluation_mode=evaluation_mode,
        )

    @property
    def dim(self) -> int:
        if self._operator_collection.static_hamiltonian is not None:
            return self._operator_collection.static_hamiltonian.shape[-1]
        elif self._operator_collection.hamiltonian_operators is not None:
            return self._operator_collection.hamiltonian_operators[0].shape[-1]
        elif self._operator_collection.static_dissipators is not None:
            return self._operator_collection.static_dissipators[0].shape[-1]
        else:
            return self._operator_collection.dissipator_operators[0].shape[-1]

    @property
    def signals(self) -> Tuple[SignalList]:
        """Gets the Model's Signals.

        Returns:
            Tuple[] with 0th entry storing the Hamiltonian signals
            and the 1st entry storing the dissipator signals.
        """
        return (self._hamiltonian_signals, self._dissipator_signals)

    @signals.setter
    def signals(self, new_signals: Tuple[List[Signal]]):
        """Set signals.

        Raises:
            QiskitError: If signals incompatible with operator structure.
        """
        hamiltonian_signals, dissipator_signals = new_signals

        # set Hamiltonian signals
        if hamiltonian_signals is None:
            self._hamiltonian_signals = None
        elif hamiltonian_signals is not None and self.get_hamiltonian_operators() is None:
            raise QiskitError("Hamiltonian signals must be None if hamiltonian_operators is None.")
        else:
            # if signals is a list, instantiate a SignalList
            if isinstance(hamiltonian_signals, list):
                hamiltonian_signals = SignalList(hamiltonian_signals)

            # if it isn't a SignalList by now, raise an error
            if not isinstance(hamiltonian_signals, SignalList):
                raise QiskitError("Hamiltonian signals specified in unaccepted format.")

            # verify signal length is same as operators
            if len(hamiltonian_signals) != len(self.get_hamiltonian_operators()):
                raise QiskitError(
                    "Hamiltonian signals need to have the same length as Hamiltonian operators."
                )

            self._hamiltonian_signals = hamiltonian_signals

        # set dissipator signals
        if dissipator_signals is None:
            if self.get_dissipator_operators() is not None:
                dissipator_signals = SignalList([1.0] * len(self.get_dissipator_operators()))
            self._dissipator_signals = dissipator_signals
        elif dissipator_signals is not None and self.get_dissipator_operators() is None:
            raise QiskitError("Dissipator signals must be None if dissipator_signals is None.")
        else:
            # if signals is a list, instantiate a SignalList
            if isinstance(dissipator_signals, list):
                dissipator_signals = SignalList(dissipator_signals)

            # if it isn't a SignalList by now, raise an error
            if not isinstance(dissipator_signals, SignalList):
                raise QiskitError("Dissipator signals specified in unaccepted format.")

            # verify signal length is same as operators
            if len(dissipator_signals) != len(self.get_dissipator_operators()):
                raise QiskitError(
                    "Dissipator signals need to have the same length as dissipator operators."
                )

            self._dissipator_signals = dissipator_signals

    def get_static_hamiltonian(self, in_frame_basis: Optional[bool] = False) -> Array:
        """Get the constant hamiltonian term.

        Args:
            in_frame_basis: Flag for whether the returned static_operator should be
            in the basis in which the frame is diagonal.
        Returns:
            The static operator term.
        """
        op = self._operator_collection.static_hamiltonian
        if not in_frame_basis and self.rotating_frame is not None:
            return self.rotating_frame.operator_out_of_frame_basis(op)
        else:
            return op

    def set_static_hamiltonian(
        self,
        new_static_hamiltonian: Array,
        operator_in_frame_basis: Optional[bool] = False,
    ):
        """Set the constant Hamiltonian term.
        Note that if the model has a rotating frame this will override
        any contributions to the static term due to the frame transformation.

        Args:
            new_static_hamiltonian: The static operator operator.
            operator_in_frame_basis: Whether `new_static_operator` is already in the rotating
            frame basis.
        """
        if new_static_hamiltonian is None:
            self._operator_collection.static_hamiltonian = None
        else:
            if not operator_in_frame_basis and self.rotating_frame is not None:
                new_static_hamiltonian = self.rotating_frame.operator_into_frame_basis(
                    new_static_hamiltonian
                )

            self._operator_collection.static_hamiltonian = new_static_hamiltonian

    def get_hamiltonian_operators(self, in_frame_basis: Optional[bool] = False) -> Tuple[Array]:
        """Get the Hamiltonian operators, either in the frame basis or not.

        Args:
            in_frame_basis: Whether to return in frame basis or not.
        Returns:
            Hamiltonian operators.
        """
        ham_ops = self._operator_collection.hamiltonian_operators
        if not in_frame_basis and self.rotating_frame is not None:
            ham_ops = self.rotating_frame.operator_out_of_frame_basis(ham_ops)

        return ham_ops

    def get_static_dissipators(self, in_frame_basis: Optional[bool] = False) -> Tuple[Array]:
        """Get the static dissipators, either in the frame basis or not.

        Args:
            in_frame_basis: Whether to return in frame basis or not.
        Returns:
            Dissipator operators.
        """
        diss_ops = self._operator_collection.static_dissipators
        if not in_frame_basis and self.rotating_frame is not None:
            diss_ops = self.rotating_frame.operator_out_of_frame_basis(diss_ops)

        return diss_ops

    def get_dissipator_operators(self, in_frame_basis: Optional[bool] = False) -> Tuple[Array]:
        """Get the Dissipator operators, either in the frame basis or not.

        Args:
            in_frame_basis: Whether to return in frame basis or not.
        Returns:
            Dissipator operators.
        """
        diss_ops = self._operator_collection.dissipator_operators
        if not in_frame_basis and self.rotating_frame is not None:
            diss_ops = self.rotating_frame.operator_out_of_frame_basis(diss_ops)

        return diss_ops

    @property
    def evaluation_mode(self) -> str:
        """Numerical evaluation mode of the model.

        Available options:

            - 'dense': Stores Hamiltonian and dissipator terms as dense
               Array types.
            - 'dense_vectorized': Stores the Hamiltonian and dissipator
              terms as (dim^2,dim^2) matrices that acts on a vectorized
              density matrix by left-multiplication. Allows for direct evaluate generator.
            - 'sparse': Like dense, but stores Hamiltonian components with
              `csr_matrix` types. Outputs will be dense if a 2d frame operator is
              used. Not compatible with jax.
            - `sparse_vectorized': Like dense_vectorized, but stores everything as csr_matrices.
        """
        return self._evaluation_mode

    @evaluation_mode.setter
    def evaluation_mode(self, new_mode: str):
        """Sets evaluation mode.

        Args:
            new_mode: String specifying new mode. Available options
                      are 'dense', 'sparse', 'dense_vectorized', and 'sparse_vectorized'.
                      See property doc string for details.

        Raises:
            NotImplementedError: if new_mode is not one of the above
            supported evaluation modes.
        """
        if new_mode != self._evaluation_mode:
            self._operator_collection = self.construct_operator_collection(
                evaluation_mode=new_mode,
                static_hamiltonian=self._operator_collection.static_hamiltonian,
                hamiltonian_operators=self._operator_collection.hamiltonian_operators,
                static_dissipators=self._operator_collection.static_dissipators,
                dissipator_operators=self._operator_collection.dissipator_operators,
            )

            self.vectorized_operators = "vectorized" in new_mode
            self._evaluation_mode = new_mode

    @property
    def rotating_frame(self):
        return self._rotating_frame

    @rotating_frame.setter
    def rotating_frame(self, rotating_frame: Union[Operator, Array, RotatingFrame]):
        new_frame = RotatingFrame(rotating_frame)

        # convert static hamiltonian to new frame setup
        static_ham = self.get_static_hamiltonian(in_frame_basis=True)
        if static_ham is not None:
            static_ham = -1j * static_ham

        new_static_hamiltonian = GeneratorModel.transfer_static_operator_between_frames(
            static_ham,
            new_frame=new_frame,
            old_frame=self.rotating_frame,
        )

        if new_static_hamiltonian is not None:
            new_static_hamiltonian = 1j * new_static_hamiltonian

        # convert hamiltonian operators and dissipator operators
        ham_ops = self.get_hamiltonian_operators(in_frame_basis=True)
        static_diss_ops = self.get_static_dissipators(in_frame_basis=True)
        diss_ops = self.get_dissipator_operators(in_frame_basis=True)

        new_hamiltonian_operators = GeneratorModel.transfer_operators_between_frames(
            ham_ops,
            new_frame=new_frame,
            old_frame=self.rotating_frame,
        )
        new_static_dissipators = GeneratorModel.transfer_operators_between_frames(
            static_diss_ops,
            new_frame=new_frame,
            old_frame=self.rotating_frame,
        )
        new_dissipator_operators = GeneratorModel.transfer_operators_between_frames(
            diss_ops,
            new_frame=new_frame,
            old_frame=self.rotating_frame,
        )

        self._rotating_frame = new_frame

        self._operator_collection = self.construct_operator_collection(
            evaluation_mode=self.evaluation_mode,
            static_hamiltonian=new_static_hamiltonian,
            hamiltonian_operators=new_hamiltonian_operators,
            static_dissipators=new_static_dissipators,
            dissipator_operators=new_dissipator_operators,
        )

    def evaluate_hamiltonian(self, time: float, in_frame_basis: Optional[bool] = False) -> Array:
        """Evaluates Hamiltonian matrix at a given time.

        Args:
            time: The time at which to evaluate the hamiltonian.
            in_frame_basis: Whether to evaluate in the basis in which
                the frame operator is diagonal.
        Returns:
            Array: Hamiltonian matrix."""

        hamiltonian_sig_vals = None
        if self._hamiltonian_signals is not None:
            hamiltonian_sig_vals = self._hamiltonian_signals(time)

        ham = self._operator_collection.evaluate_hamiltonian(hamiltonian_sig_vals)
        if self.rotating_frame.frame_diag is not None:
            ham = self.rotating_frame.operator_into_frame(
                time,
                ham,
                operator_in_frame_basis=True,
                return_in_frame_basis=in_frame_basis,
                vectorized_operators=self.vectorized_operators,
            )

        return ham

    def evaluate(self, time: float, in_frame_basis: Optional[bool] = False) -> Array:
        hamiltonian_sig_vals = None
        if self._hamiltonian_signals is not None:
            hamiltonian_sig_vals = self._hamiltonian_signals(time)

        dissipator_sig_vals = None
        if self._dissipator_signals is not None:
            dissipator_sig_vals = self._dissipator_signals(time)

        if self.vectorized_operators:
            out = self._operator_collection.evaluate(hamiltonian_sig_vals, dissipator_sig_vals)
            return self.rotating_frame.vectorized_map_into_frame(
                time, out, operator_in_frame_basis=True, return_in_frame_basis=in_frame_basis
            )
        else:
            raise NotImplementedError(
                "Non-vectorized Lindblad models cannot be represented without a given state."
            )

    def evaluate_rhs(
        self, time: Union[float, int], y: Array, in_frame_basis: Optional[bool] = False
    ) -> Array:
        """Evaluates the Lindblad model at a given time.

        Args:
            time: time at which the model should be evaluated.
            y: Density matrix as an (n,n) Array if not using a
               vectorized evaluation_mode or an (n^2) Array if
               using vectorized evaluation.
            in_frame_basis: whether the density matrix is in the
                            frame already, and if the final result
                            is returned in the rotating frame or not.

        Returns:
            Array: Either the evaluated generator or the state.
        """

        hamiltonian_sig_vals = None
        if self._hamiltonian_signals is not None:
            hamiltonian_sig_vals = self._hamiltonian_signals(time)

        dissipator_sig_vals = None
        if self._dissipator_signals is not None:
            dissipator_sig_vals = self._dissipator_signals(time)

        if self.rotating_frame.frame_diag is not None:

            # Take y out of the frame, but keep in the frame basis
            rhs = self.rotating_frame.operator_out_of_frame(
                time,
                y,
                operator_in_frame_basis=in_frame_basis,
                return_in_frame_basis=True,
                vectorized_operators=self.vectorized_operators,
            )

            rhs = self._operator_collection.evaluate_rhs(
                hamiltonian_sig_vals, dissipator_sig_vals, rhs
            )

            # Put rhs back into the frame, potentially converting its basis.
            rhs = self.rotating_frame.operator_into_frame(
                time,
                rhs,
                operator_in_frame_basis=True,
                return_in_frame_basis=in_frame_basis,
                vectorized_operators=self.vectorized_operators,
            )

        else:
            rhs = self._operator_collection.evaluate_rhs(
                hamiltonian_sig_vals, dissipator_sig_vals, y
            )

        return rhs

    @classmethod
    def construct_operator_collection(
        cls,
        evaluation_mode: str,
        static_hamiltonian: Union[None, Array, csr_matrix],
        hamiltonian_operators: Union[None, Array, List[csr_matrix]],
        static_dissipators: Union[None, Array, csr_matrix],
        dissipator_operators: Union[None, Array, List[csr_matrix]],
    ) -> BaseLindbladOperatorCollection:
        """Sets evaluation mode.

        Args:
            evaluation_mode: String specifying new mode. Available options
                             are 'dense', 'sparse', 'dense_vectorized', and 'sparse_vectorized'.
                             See property doc string for details.
            static_hamiltonian: Constant part of the Hamiltonian.
            hamiltonian_operators: Operators in Hamiltonian with time-dependent coefficients.
            static_dissipators: Dissipation operators with coefficient 1.
            dissipator_operators: Dissipation operators with variable coefficients.

        Raises:
            NotImplementedError: if evaluation_mode is not one of the above
            supported evaluation modes.
        """
        if evaluation_mode == "dense":
            CollectionClass = DenseLindbladCollection
        elif evaluation_mode == "sparse":
            CollectionClass = SparseLindbladCollection
        elif evaluation_mode == "dense_vectorized":
            CollectionClass = DenseVectorizedLindbladCollection
        elif evaluation_mode == "sparse_vectorized":
            CollectionClass = SparseVectorizedLindbladCollection
        else:
            raise NotImplementedError(
                "Evaluation mode '"
                + str(evaluation_mode)
                + "' is not supported. Call help("
                + str(cls.__name__)
                + ".evaluation_mode) for available options."
            )

        return CollectionClass(
            static_hamiltonian=static_hamiltonian,
            hamiltonian_operators=hamiltonian_operators,
            static_dissipators=static_dissipators,
            dissipator_operators=dissipator_operators,
        )
