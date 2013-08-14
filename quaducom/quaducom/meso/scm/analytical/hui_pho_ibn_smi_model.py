'''
Created on Apr 20, 2012

model of single fiber composite by Hui, Phoenix, Ibnabeljalil and Smith

@author: rostar
'''

from etsproxy.traits.api import HasTraits, Float, Property, cached_property
import numpy as np
from scipy.special import expi
from scipy.integrate import cumtrapz

class SFC_Hui(HasTraits):

    l0 = Float
    d = Float
    tau = Float
    sigma0 = Float
    rho = Float

    def delta(self, sigma):
        '''stress transfer lenth'''
        return self.d * sigma / 2. / self.tau

    def Lambda(self, sigma):
        '''mean number of flaws with strength less than sigma'''
        return (sigma/self.sigma0)**self.rho / self.l0
    
    def F(self, sigma, l):
        '''probability of failure at stress sigma and length l'''
        return 1. - np.exp(-l*self.Lambda(sigma))

    lambd = Property(Float, depends_on='rho')
    @cached_property
    def _get_lambd(self):
        return self.rho/(1 + self.rho)

    sigmac = Property(Float, depends_on='sigma0, l0, tau, d, rho')
    @cached_property
    def _get_sigmac(self):
        '''dimensionless stress'''
        return self.sigma0 * (2. * self.l0 * self.tau / self.d / self.sigma0) ** (self.lambd / self.rho)

    deltac = Property(Float, depends_on='sigma0, l0, tau, d, rho')
    @cached_property
    def _get_deltac(self):
        '''dimensionless length'''
        return self.l0 * (self.d * self.sigma0 / 2. / self.l0 / self.tau) ** self.lambd

    def Lambda_tilde(self, s):
        '''mean number of flaws with strength less than s'''
        return s ** self.rho

    def h(self, s):
        '''hazard rate at s'''
        return self.rho * s ** (self.rho - 1.)
    
    def A0(self, s):
        Y = s**(self.rho+1)/2.
        def Phi(x):
            return self.lambd * (0.577215664901532 + np.log(x) - expi(-x))
        def Psi(x):
            return np.exp(-2.*Phi(x))
        return s**(2.*self.rho) * np.exp(self.lambd * s ** (self.rho + 1)) * Psi(Y)

    def p1(self, s, x):
        return self.A0(s) * np.exp(-s**self.rho * x)
    
    def p2(self, s, x):
        def integ_scalar(s, x):
            t = np.linspace(x, s, 200)
            return np.trapz(self.A0(t)/t * np.exp(-t**self.rho * (x + t/2.)), t)
        integ_vect = np.vectorize(integ_scalar)
        return 2. * self.rho * integ_vect(s, x) + np.nan_to_num(self.p1(x, x))

    def p22(self, s, x):
        def integ_scalar(s, x):
            t = np.linspace(x, s, 200)
            def integrant(t):
                return t**(2.*self.rho) * np.exp(self.lambd * t ** (self.rho + 1) -2.*self.lambd * (0.577215664901532 + np.log(t**(self.rho+1)/2.) - expi(-t**(self.rho+1)/2.)) -t**self.rho * (x + t/2.)) /t
            return np.trapz(integrant(t), t)
        integ_vect = np.vectorize(integ_scalar)
        return 2. * self.rho * integ_vect(s, x) + np.nan_to_num(self.p1(x, x))

    def p3(self, x):
        return self.p22(2 * x, x)

    def p(self, s, x):
        p1 = np.nan_to_num(self.p1(s, x)) * (x >= s)
        p2 = np.nan_to_num(self.p22(s, x)) * (x < s) * (x >= s / 2.)
        p3 = np.nan_to_num(self.p3(x)) * (x < s / 2.)
        p = p1 + p2 + p3
        p_inf = np.trapz(p, x)
        return p / p_inf

if __name__ == '__main__':
    from matplotlib import pyplot as plt
    sfc = SFC_Hui(l0=1., d=0.007, tau=0.1, sigma0=2200., rho=5.0)
    for rho in np.array([1., 3., 5., 10., 20.]):
        sfc.rho = rho
        x = np.linspace(0.01, 3.0, 200)
        pdf = sfc.p(3., x)
        cdf = np.hstack((0., cumtrapz(pdf, x)))
        plt.plot(x, cdf, label=str(rho))
    plt.legend()
    plt.show()
    