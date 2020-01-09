# -------------------------------------------------------------
# In this program we implemented of Algorithm 2 of the paper for the Fitzhugh-Nagumo equation.
# @author: J.Cricelio Montesinos-López and Maria L. Daza-Torres
#  --------------------------------------------------------------

import numpy as np
from numba import jit
import numpy.random as nr
from scipy.stats import norm as gaussian
import matplotlib.pyplot as plt
from matplotlib import rcParams
from scipy.special import gammaln
from scipy.stats import beta
from pytwalk import pytwalk
from FM_Ex2 import u_true, U_xt,  rungekuttaodeint

rcParams["font.family"] = "Times New Roman"
rcParams['font.size'] = 11.5

# =============================================================================
# Fixed parameters
# =============================================================================
n_obs = 8           # Number of observation
sigma_true = 0.007  # True variance for the data

t0 = 0      # Initial time
tau = 0.4   # Final time
# Boundary
x0 = 0
xN = 1

n_m = 8                 # number of times that the observation grid is divided
nx = n_m * (n_obs + 2)  # Number of nodes in x
dx = 1 / nx             # Spatial step size
alpha = 4 / 3           # Parameter for the stability
dt = dx ** 2 / alpha    # Temporal step size

grid_t = np.arange(t0, tau + dt, dt)  # Temporal grid
grid_x = np.arange(x0, xN, dx)        # Spatial grid
M = len(grid_t)                       # Number of time steps
N = len(grid_x[1:])                   # Dimension of state variables


t_obs = tau                  # Time at which the data are observed
x_obs = grid_x[::n_m][1:-1]  # Location where data are observed
theta = 0.3                  # Parameter in the Fitzhugh-Nagumo equation

# Auxiliary parameters
Alpha = np.sqrt(2 * np.pi) / 20.0
BoundForEABF = (Alpha / n_obs) * sigma_true  # Error bound Eq. (21)
p = 1 / dx ** 2
xl = 0.00001
xr = 0.99999


def fm_fNagumo_obs(theta):
    """
        Function to compute the numerical solution for the Fitzhugh-Nagumo equation on the observational mesh.

        Parameters
        ---------
        theta: float
           Parameter in the Fitzhugh-Nagumo equation

        Returns
        -------
        sol_obs: float
           Numerical solution in (x,t) and parameter theta
    """
    X, err = U_xt(dx, dt, theta)
    sol_obs = X[-1][(n_m - 1)::n_m][:-1]
    return sol_obs


def make_data(sigma, theta):
    """
        Function to generate synthetic data, data = FM(theta) + rnorm(0,sigma)

        Parameters
        ---------
        sigma: float
            Variance for data
        theta: float
           Parameter in Fisher's equation

        Returns
        -------
        data: float
           Synthetic data
    """
    nr.seed(23)
    u_obs = u_true(x_obs, t_obs, theta)
    data = u_obs + sigma * gaussian.rvs(size=n_obs)
    nr.seed(None)
    return data


def plot_data(theta):
    """
      This function plot the exact solution for the Fisher's equation
      and the synthetic data set, at locations obs_x at time t_obs

      Parameters
      ----------
      theta: float
          Parameter in the Fisher's equation
     """
    plt.figure()
    plt.plot(x_obs, make_data(sigma_true, theta), '.')
    plt.plot(grid_x[1:], u_true(grid_x[1:], grid_t[-1], theta),"black", label='True')
    plt.xlabel(r'$x$')
    plt.ylabel(r'$u(x_{obs},t_{obs})$')
    plt.savefig("datan%ssig%s.eps" % (n_obs, sigma_true))  # Uncomment the line for saving the figure


# =============================================================================
# Inference: MCMC
# =============================================================================


Data = make_data(sigma_true, theta)  # Generate synthetic data, at locations obs_x at time t_obs
d = 1                                # We make inferences in one parameter

# Define prior parameters: Gamma(alpha, beta) prior
alp_r = 2
bet_r = 3.5

# Constants for the prior and the likelihood
alp_r1 = alp_r - 1
bet_r1 = bet_r - 1

prior_consts = gammaln(alp_r) + gammaln(bet_r) - gammaln(alp_r + bet_r)
like_const = -0.5 * d * np.log(2.0 * np.pi) - d * np.log(sigma_true)


def LogPrior(theta):
    """ Compute the Log of the prior"""
    pc = alp_r1 * np.log(theta[0]) + bet_r1 * (1 - theta[0])
    return pc - prior_consts

# Choose the numeric (numeric = True) or the exact (numeric = False) forward map to run the MCMC


numeric = True
if numeric:
    def LogLikelihood(theta):  # Numerical Log-Likelihood
        fmap_num = fm_fNagumo_obs(theta[0])
        Dtheta = (Data-fmap_num)/sigma_true
        like = like_const - 0.5 * np.linalg.norm(Dtheta) ** 2
        return like
else:
    def LogLikelihood(theta):  # Theorical Log-Likelihood
        fmap_teo = u_true(x_obs, t_obs, theta)
        Dtheta = (Data - fmap_teo) / sigma_true
        like = like_const - 0.5 * np.linalg.norm(Dtheta) ** 2
        return like


def Energy(theta):
    """ - logarithm of the posterior distribution (could it be proportional) """
    return -(LogLikelihood(theta) + LogPrior(theta))


def Supp(theta):
    """ Check if theta is in the support of the posterior distribution"""
    rt = ((theta[0] > 0) and (theta[0] < 1))
    return rt

def SimInit():
    """ Function to simulate initial values for the gamma distribution """
    r = beta.rvs(alp_r, bet_r)
    return np.array([r])

# =============================================================================
# Run the twalk MCMC with T iterations
# =============================================================================
# First, we run the chain using the exact solution for the forward mapping
#  changing numeric = False


twalk = pytwalk(n=d, U=Energy, Supp=Supp)       # Open the t-walk object
T = 1000#200000                                      # Number of simulations in the MCMC (Chain length)
twalk.Run(T=T, x0=SimInit(), xp0=SimInit())     # Run the t-walk with two initial values for theta
hpd_index = np.argsort(twalk.Output[:, -1])     # Maximum a posteriori index
MAP = twalk.Output[hpd_index[0], :-1]           # MAP


def plot_post():
    plt.figure()
    start = int(.4 * T)                                                     # Burning
    Out_r = twalk.Output[:, 0][start:]                                      # Output without burning
    rt = plt.hist(Out_r, bins=20, label='Numeric',density=True)             # Histogram of the simulations
    plt.axvline(theta, ymax=rt[0].max() * 0.05, color='r', label='True')    # True parameter
    xalph = np.linspace(Out_r.min(), Out_r.max(), 100)
    plt.plot(xalph, beta.pdf(xalph, alp_r, bet_r), 'g-', lw=1.5, alpha=0.6, label="Prior")    # Prior
    plt.xlabel('r')
    plt.ylabel('Density')
    plt.legend()


plot_post()                     # Uncomment the line for plot the posterior distribution, Example 5.
plt.figure()
plt.plot(-twalk.Output[:, -1])  # Uncomment the line for plot the log-posterior distribution, Example 5.

# # Uncomment the line for saving the output
# if numeric:
#     np.savetxt('output%s_numeric.out' % T, twalk.Output)
# else:
#     np.savetxt('output%s_true.out' % T, twalk.Output)
