# -*- coding: utf-8 -*-

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
# pylint: disable=invalid-name,no-member,attribute-defined-outside-init

r"""
=============================================================
Differential equations solvers (:mod:`qiskit_dynamics.solve`)
=============================================================

This module provides high level functions for solving classes of
Differential Equations (DEs), described below.

1. Ordinary Differential Equations (ODEs)
#########################################

The most general class of DEs we consider are ODEs, which are of the form:

.. math::

    \dot{y}(t) = f(t, y(t)),

Where :math:`f` is called the Right-Hand Side (RHS) function.
ODEs can be solved by calling the :meth:`~qiskit_dynamics.solve_ode` function.

2. Linear Matrix Differential Equations (LMDEs)
###############################################

LMDEs are a specialized subclass of ODEs of importance in quantum theory. Most generally,
an LMDE is an ODE for which the the RHS function :math:`f(t, y)` is *linear* in the second
argument. Numerical methods for LMDEs typically assume a *standard form*

.. math::

    f(t, y) = G(t)y,

where :math:`G(t)` is a square matrix-valued function called the *generator*, and
the state :math:`y(t)` must be an array of appropriate shape. Note that any LMDE in the more
general sense (not in *standard form*) can be restructured into one of standard form via suitable
vectorization.

The function :meth:`~qiskit_dynamics.de.solve_lmde` provides access to solvers for LMDEs in
standard form, specified in terms of a representation of the generator :math:`G(t)`,
either as a Python ``Callable`` function or subclasses of
:class:`~qiskit_dynamics.models.generator_models.BaseGeneratorModel`.

Note that methods available via :meth:`~qiskit_dynamics.solve_ode` are also available through
:meth:`~qiskit_dynamics.de.solve_lmde`:

    * If the generator is supplied as a ``Callable``, the standard RHS function
      :math:`f(t, y) = G(t)y` is automatically constructed.
    * If the generator supplied is a subclass of
      :class:`~qiskit_dynamics.models.generator_models.BaseGeneratorModel` which is not in standard
      form, it is delegated to :meth:`~qiskit_dynamics.solve_ode`.



.. currentmodule:: qiskit_dynamics.solve

.. autosummary::
   :toctree: ../stubs/

   solve_ode
   solve_lmde
"""

from typing import Optional, Union, Callable, Tuple, List
import inspect

from scipy.integrate import OdeSolver

# pylint: disable=unused-import
from scipy.integrate._ivp.ivp import OdeResult

from qiskit.circuit import Gate, QuantumCircuit
from qiskit.quantum_info.operators.base_operator import BaseOperator
from qiskit.quantum_info.operators.channel.quantum_channel import QuantumChannel
from qiskit.quantum_info.states.quantum_state import QuantumState
from qiskit.quantum_info import SuperOp, Operator

from qiskit import QiskitError
from qiskit_dynamics import dispatch
from qiskit_dynamics.dispatch import Array, requires_backend

from .solvers.fixed_step_solvers import scipy_expm_solver, jax_expm_solver
from .solvers.scipy_solve_ivp import scipy_solve_ivp, SOLVE_IVP_METHODS
from .solvers.jax_odeint import jax_odeint

from .models.rotating_frame import RotatingFrame
from .models.rotating_wave_approximation import rotating_wave_approximation
from .models.generator_models import BaseGeneratorModel, GeneratorModel
from .models import HamiltonianModel, LindbladModel

try:
    from jax.lax import scan
except ImportError:
    pass


ODE_METHODS = ["RK45", "RK23", "BDF", "DOP853", "Radau", "LSODA"] + ["jax_odeint"]
LMDE_METHODS = ["scipy_expm", "jax_expm"]


def solve_ode(
    rhs: Union[Callable, BaseGeneratorModel],
    t_span: Array,
    y0: Array,
    method: Optional[Union[str, OdeSolver]] = "DOP853",
    t_eval: Optional[Union[Tuple, List, Array]] = None,
    **kwargs,
):
    r"""General interface for solving Ordinary Differential Equations (ODEs).
    ODEs are differential equations of the form

    .. math::

        \dot{y}(t) = f(t, y(t)),

    where :math:`f` is a callable function and the state :math:`y(t)` is an
    arbitrarily-shaped complex :class:`Array`.

    The ``method`` argument exposes a variety of underlying ODE solvers. Optional
    arguments for any of the solver routines can be passed via ``kwargs``.
    Available methods are:

    - ``scipy.integrate.solve_ivp`` - supports methods
      ``['RK45', 'RK23', 'BDF', 'DOP853', 'Radau', 'LSODA']`` or by passing a valid
      ``scipy`` :class:`OdeSolver` instance.
    - ``jax.experimental.ode.odeint`` - accessed via passing
      ``method='jax_odeint'``.

    Results are returned as a :class:`OdeResult` object.

    Args:
        rhs: RHS function :math:`f(t, y)`.
        t_span: ``Tuple`` or ``list`` of initial and final time.
        y0: State at initial time.
        method: Solving method to use.
        t_eval: Times at which to return the solution. Must lie within ``t_span``. If unspecified,
                the solution will be returned at the points in ``t_span``.
        kwargs: Additional arguments to pass to the solver.

    Returns:
        OdeResult: Results object.

    Raises:
        QiskitError: If specified method does not exist.
    """

    if method not in ODE_METHODS and not (
        inspect.isclass(method) and issubclass(method, OdeSolver)
    ):
        raise QiskitError("Method " + str(method) + " not supported by solve_ode.")

    t_span = Array(t_span)
    y0 = Array(y0)

    if isinstance(rhs, BaseGeneratorModel):
        _, solver_rhs, y0 = setup_generator_model_rhs_y0_in_frame_basis(rhs, y0)
    else:
        solver_rhs = rhs

    # solve the problem using specified method
    if method in SOLVE_IVP_METHODS or (inspect.isclass(method) and issubclass(method, OdeSolver)):
        results = scipy_solve_ivp(solver_rhs, t_span, y0, method, t_eval, **kwargs)
    elif isinstance(method, str) and method == "jax_odeint":
        results = jax_odeint(solver_rhs, t_span, y0, t_eval, **kwargs)

    # convert results to correct basis if necessary
    if isinstance(rhs, BaseGeneratorModel):
        results.y = results_y_out_of_frame_basis(rhs, Array(results.y), y0.ndim)

    return results


def solve_lmde(
    generator: Union[Callable, BaseGeneratorModel],
    t_span: Array,
    y0: Array,
    method: Optional[Union[str, OdeSolver]] = "DOP853",
    t_eval: Optional[Union[Tuple, List, Array]] = None,
    **kwargs,
):
    r"""General interface for solving Linear Matrix Differential Equations (LMDEs)
    in standard form:

    .. math::

        \dot{y}(t) = G(t)y(t)

    where :math:`G(t)` is a square matrix valued-function called the *generator*,
    and :math:`y(t)` is an :class:`Array` of appropriate shape. The generator :math:`G(t)`
    may either be specified as a Python ``Callable`` function,
    or as an instance of a :class:`~qiskit_dynamics.models.BaseGeneratorModel` subclass.

    The ``method`` argument exposes solvers specialized to both LMDEs, as
    well as general ODE solvers. If the method is not specific to LMDEs,
    the problem will be passed to :meth:`~qiskit_dynamics.solve_ode` by automatically setting
    up the RHS function :math:`f(t, y) = G(t)y`.

    We note that, while all :class:`~qiskit_dynamics.models.BaseGeneratorModel` subclasses
    represent LMDEs, they are not all by-default in standard form, and as such, accessing
    LMDE-specific methods requires converting them into standard form. See, for example,
    :meth:`~qiskit_dynamics.models.LindbladModel.set_evaluation_mode` for details. Regardless,
    in general, for general ODE methods,
    subclasses of :class:`~qiskit_dynamics.models.BaseGeneratorModel`
    will be fed directly through to :meth:`~qiskit_dynamics.solve_ode`, allowing
    :meth:`~qiskit_dynamics.solve_lmde` to serve as a general solver interface for
    :class:`~qiskit_dynamics.models.BaseGeneratorModel` subclasses.

    Optional arguments for any of the solver routines can be passed via ``kwargs``.
    Available LMDE-specific methods are:

    - ``'scipy_expm'``: A matrix-exponential solver using ``scipy.linalg.expm``.
                        Requires additional kwarg ``max_dt``.
    - ``'jax_expm'``: A ``jax``-based exponential solver. Requires additional kwarg ``max_dt``.

    Results are returned as a :class:`OdeResult` object.

    Args:
        generator: Representation of generator function :math:`G(t)`.
        t_span: ``Tuple`` or `list` of initial and final time.
        y0: State at initial time.
        method: Solving method to use.
        t_eval: Times at which to return the solution. Must lie within ``t_span``. If unspecified,
                the solution will be returned at the points in ``t_span``.
        kwargs: Additional arguments to pass to the solver.

    Returns:
        OdeResult: Results object.

    Raises:
        QiskitError: If specified method does not exist,
                     if dimension of ``y0`` is incompatible with generator dimension,
                     or if an LMDE-specific method is passed with a LindbladModel.
    """

    # lmde-specific methods can't be used with LindbladModel unless vectorized
    if (
        isinstance(generator, LindbladModel)
        and ("vectorized" not in generator.evaluation_mode)
        and (method in LMDE_METHODS)
    ):
        raise QiskitError(
            """LMDE-specific methods with LindbladModel requires setting a
               vectorized evaluation mode."""
        )

    # if method is an ODE method, delegate to solve ODE
    if method not in LMDE_METHODS:
        if method in ODE_METHODS or (inspect.isclass(method) and issubclass(method, OdeSolver)):
            if isinstance(generator, BaseGeneratorModel):
                rhs = generator
            else:
                # treat generator as a function
                def rhs(t, y):
                    return generator(t) @ y

            return solve_ode(rhs, t_span, y0, method=method, t_eval=t_eval, **kwargs)
        else:
            raise QiskitError("Method " + str(method) + " not supported by solve_lmde.")

    t_span = Array(t_span)
    y0 = Array(y0)

    # setup generator and rhs functions to pass to numerical methods
    if isinstance(generator, BaseGeneratorModel):
        solver_generator, _, y0 = setup_generator_model_rhs_y0_in_frame_basis(generator, y0)
    else:
        solver_generator = generator

    if method == "scipy_expm":
        results = scipy_expm_solver(solver_generator, t_span, y0, t_eval=t_eval, **kwargs)
    elif method == "jax_expm":
        results = jax_expm_solver(solver_generator, t_span, y0, t_eval=t_eval, **kwargs)

    # convert results to correct basis if necessary
    if isinstance(generator, BaseGeneratorModel):
        results.y = results_y_out_of_frame_basis(generator, Array(results.y), y0.ndim)

    return results


def setup_generator_model_rhs_y0_in_frame_basis(
    generator_model: BaseGeneratorModel, y0: Array
) -> Tuple[Callable, Callable, Array]:
    """Helper function for setting up a subclass of
    :class:`~qiskit_dynamics.models.BaseGeneratorModel` to be solved in the frame basis.

    Args:
        generator_model: Subclass of :class:`~qiskit_dynamics.models.BaseGeneratorModel`.
        y0: Initial state.

    Returns:
        Callable for generator in frame basis, Callable for RHS in frame basis, and y0
        transformed to frame basis.
    """

    if (
        isinstance(generator_model, LindbladModel)
        and "vectorized" in generator_model.evaluation_mode
    ):
        if generator_model.rotating_frame.frame_basis is not None:
            y0 = generator_model.rotating_frame.vectorized_frame_basis_adjoint @ y0
    elif isinstance(generator_model, LindbladModel):
        y0 = generator_model.rotating_frame.operator_into_frame_basis(y0)
    elif isinstance(generator_model, GeneratorModel):
        y0 = generator_model.rotating_frame.state_into_frame_basis(y0)

    # define rhs functions in frame basis
    def generator(t):
        return generator_model(t, in_frame_basis=True)

    def rhs(t, y):
        return generator_model(t, y, in_frame_basis=True)

    return generator, rhs, y0


def results_y_out_of_frame_basis(
    generator_model: BaseGeneratorModel, results_y: Array, y0_ndim: int
) -> Array:
    """Convert the results of a simulation for :class:`~qiskit_dynamics.models.BaseGeneratorModel`
    out of the frame basis.

    Args:
        generator_model: Subclass of :class:`~qiskit_dynamics.models.BaseGeneratorModel`.
        results_y: Array whose first index corresponds to the evaluation points of the state
                   for the results of ``solve_lmde`` or ``solve_ode``.
        y0_ndim: Number of dimensions of initial state.

    Returns:
        Callable for generator in frame basis, Callable for RHS in frame basis, and y0
        transformed to frame basis.
    """
    # for left multiplication cases, if number of input dimensions is 1
    # vectorized basis transformation requires transposing before and after
    if y0_ndim == 1:
        results_y = results_y.T

    if (
        isinstance(generator_model, LindbladModel)
        and "vectorized" in generator_model.evaluation_mode
    ):
        if generator_model.rotating_frame.frame_basis is not None:
            results_y = generator_model.rotating_frame.vectorized_frame_basis @ results_y
    elif isinstance(generator_model, LindbladModel):
        results_y = generator_model.rotating_frame.operator_out_of_frame_basis(results_y)
    elif isinstance(generator_model, GeneratorModel):
        results_y = generator_model.rotating_frame.state_out_of_frame_basis(results_y)

    if y0_ndim == 1:
        results_y = results_y.T

    return results_y
