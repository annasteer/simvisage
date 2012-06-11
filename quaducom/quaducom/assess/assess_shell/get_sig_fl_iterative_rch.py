'''
Created on Jun 23, 2010

@author: alexander
'''

from etsproxy.traits.api import \
    Float, Instance, Array, Int, Property, cached_property, on_trait_change, Bool, \
    HasTraits, File, Event, Trait

from etsproxy.traits.ui.api import \
    View, Item, FileEditor, HSplit, Group, VSplit, \
    Handler

from etsproxy.traits.ui.menu import \
    Action, CloseAction, HelpAction, Menu, \
    MenuBar, NoButtons, Separator, ToolBar

from etsproxy.pyface.api import ImageResource

from ibvpy.mats.mats_explore import MATSExplore
from ibvpy.mats.mats2D.mats2D_explore import MATS2DExplore

from numpy import array, loadtxt, arange, sqrt, zeros, arctan, sin, cos, ones_like, \
                vstack, savetxt, hstack, argsort, fromstring, zeros_like, \
                copy as ncopy, c_, newaxis, argmax, where, argsort, sqrt, frompyfunc, \
                max as ndmax, dot, fabs, arange, ones, ceil

from mathkit.mfn import MFnLineArray

from scipy.optimize import fsolve

data_file_editor = FileEditor(filter = ['*.DAT'])

from matresdev.db.simdb import SimDB
simdb = SimDB()

class SigFlCalib(HasTraits):

    #---------------------------------------------------------------
    # material properties textile reinforcement
    #-------------------------------------------------------------------

    # security factor 'gamma_tex' for the textile reinforcement
    #
#    gamma_tex = Float(1.5, input = True)

    # reduction factor to drive the characteristic value from mean value
    # of the experiment (EN DIN 1990)
    #
#    beta = Float(0.81, input = True)

    #---------------------------------------------------------------
    # material properties concrete
    #-------------------------------------------------------------------

    # characteristic compressive force [MPa]
    #
    f_ck = Float(60.0, input = True)

#    # mean value of the compressive force [MPa]
#    # @todo: how to get the realistic concrete strength (use the measured mean value?)
#
#    f_cm = Property( Float ) 
#    def _get_f_cm( self ):
#        return 1.25 * self.f_ck

#    # security factor 'gamma_c' for hight strength concrete (>C55/67)
#    #
#    gamma_c = Property( Float )
#    def _get_gamma_c( self ):
#        return 1.5 * ( 1 / ( 1.1 - self.f_ck / 500. ) )
#
#    # design value of the compressive force [MPa]
#    #
#    f_cd = Property( Float )
#    def _get_f_cd( self ):
#        return 0.85 * self.f_ck / self.gamma_c

    # compressive strain at the top at rupture [-]
    # value measured at the experiment (with DMS)
    # for 0: about 3.3
    # for 90: about 3.0
    # ultimute strain theoreticaly (Brockman): about 4.5
    # NOTE: strain was meassured at a distance of 5 cm
    #
    eps_c = Float(0.003, input = True) # 3 promile

    #---------------------------------------------------------------
    # properties of the composite cross section
    #-------------------------------------------------------------------

    # thickness of reinforced cross section
    #
    thickness = Float(0.06, geo_input = True)

    # total number of reinforcement layers [-]
    # 
    n_layers = Float(12, geo_input = True)

    # spacing between the layers [m]
    #
    s_tex_z = Property(depends_on = '+geo_input')
    @cached_property
    def _get_s_tex_z(self):
        return self.thickness / (self.n_layers + 1)

    # distance from the top of each reinforcement layer [m]:
    #
    z_t_i_arr = Property(depends_on = '+geo_input')
    @cached_property
    def _get_z_t_i_arr(self):
        return array([ self.thickness - (i + 1) * self.s_tex_z for i in range(self.n_layers) ],
                      dtype = float)

    #---------------------------------------------------------------
    # properties of the bending specimens (tree point bending test):
    #---------------------------------------------------------------

    # width of the cross section [m]
    #
    width = Float(0.20, input = True)
    
    # number of rovings in 0-direction of one composite 
    # layer of the bending test [-]:
    #
    n_rovings = Int(23, input = True)

    # cross section of one roving [mm**2]:
    #
    A_roving = Float(0.461, input = True)


    # @todo: what about the global variables? remove?

#    E_yarn = Float
#    sig_comp_i_arr = Array(float)

#    eps_t_i_arr = Property( Array(float), depends_on = '+input')
#    @cached_property
#    def _get_eps_t_i_arr(self):
#        return self.layer_response( self, u )


    def layer_response_eps_t_E_yarn( self, u ):
        '''CALIBRATION: derive the unknown constitutive law of the layer
        (effective crack bridge law)
        '''
        eps_t, E_yarn = u
        # ------------------------------------                
        # derived params depending on value for 'eps_t'
        # ------------------------------------                

        thickness = self.thickness 
        z_t_i_arr = self.z_t_i_arr 

        # heights of the compressive zone:
        #
        x = abs(self.eps_c) / (abs(self.eps_c) + abs(eps_t)) * thickness
        print 'x', x

        # strain at the height of each reinforcement layer [-]:
        #
        eps_t_i_arr = eps_t / (thickness - x) * (z_t_i_arr - x)

        # use a ramp function to consider only positive strains
        eps_t_i_arr = (fabs(eps_t_i_arr) + eps_t_i_arr) / 2.0
        # print 'eps_t_i_arr', eps_t_i_arr

        # @todo: does this make sense to send this as a global variable?
        # use property instead ?!    
#        self.eps_t_i_arr = ncopy( eps_t_i_arr )

        # constitutive law of the crack bridge
        # linear elastic: effective modulus of elasticity 
        #
        eps_fail = eps_t
        sig_fail = E_yarn * eps_fail
        xdata = array([0., eps_fail ])
        ydata = array([0., sig_fail ])
        mfn_line_array = MFnLineArray(xdata = xdata, ydata = ydata)
        return x, eps_t_i_arr, mfn_line_array


    def layer_response_eps_t_eps_c( self, u ):
        '''EVALUATION: using the calibrated constitutive law of the layer
        '''
        eps_t, eps_c = u

        E_yarn = self.E_yarn

        self.eps_c = eps_c

        thickness = self.thickness 
        z_t_i_arr = self.z_t_i_arr 
        
        # ------------------------------------                
        # derived params depending on value for 'eps_t'
        # ------------------------------------                

        # heights of the compressive zone:
        #
        x = abs(eps_c) / (abs(eps_c) + abs(eps_t)) * thickness
        print 'x', x

        # strain at the height of each reinforcement layer [-]:
        #
        eps_t_i_arr = eps_t / (thickness - x) * (z_t_i_arr - x)

        # use a ramp function to consider only positive strains
        eps_t_i_arr = (fabs(eps_t_i_arr) + eps_t_i_arr) / 2.0
        # print 'eps_t_i_arr', eps_t_i_arr
#        self.eps_t_i_arr = ncopy(eps_t_i_arr)

        # construct the constitutive law of the crack bridge - linear elastic
        # with the search effective modulus of elasticity 
        #
        eps_fail = eps_t
        sig_fail = E_yarn * eps_fail

        # linear law of the crack bridge
        #-------------------------------
        # conservative for iteration of response due to imposed loads
        # 'Einwirkungsseite'
        #
        xdata = array([0., eps_fail ])
        ydata = array([0., sig_fail ])

#         # plastic law of the crack bridge
#         #-------------------------------
#         # conservative for iteration of resistance stress
#         # 'Widerstandsseite'
#        
#        xdata = array( [0, 0.01 * eps_fail, eps_fail ] )
#        ydata = array( [0, 0.99 * sig_fail, sig_fail ] )

        mfn_line_array = MFnLineArray(xdata = xdata, ydata = ydata)
        return x, eps_t_i_arr, mfn_line_array


    def get_f_t_i_arr( self, u ):
        '''tensile force at the height of each reinforcement layer [kN]:
        '''
        x, eps_t_i_arr, layer_response = self.layer_response( u )

        get_sig_t_i_arr = frompyfunc( layer_response.get_value, 1, 1 )
        sig_t_i_arr = get_sig_t_i_arr( eps_t_i_arr )

        # print 'sig_i_arr', sig_i_arr

        # tensile force of one reinforced composite layer [kN]:
        #
        n_rovings = self.n_rovings
        A_roving = self.A_roving
        f_t_i_arr = sig_t_i_arr * n_rovings * A_roving / 1000.
        # print 'f_t_i_arr', f_t_i_arr

        return x, f_t_i_arr

    def get_sig_comp_i_arr( self, u ):
        '''tensile stress at the height of each reinforcement layer [MPa]:
        '''
        x, f_t_i_arr = self.get_f_t_i_arr( u )
        return f_t_i_arr / self.width / self.s_tex_z / 1000.0

    #-----------------------------
    # for simplified constant stress-strain-diagram of the concrete (EC2)
    #-----------------------------

#    # factor [-] to calculate the value of the resulting compressive 
#    # force, i.e. f_c = fck / gamma_c 
#    # (for high strength concrete)
#    #
#    chi = Property
#    def _get_chi( self ):
#        return 1.05 - self.f_ck / 500.
#
#    # factor [-] to calculate the distance of the resulting compressive 
#    # force from the top, i.e. a = k * x
#    #
#    k = Property
#    def _get_k( self ):
#        return 1.05 - self.f_ck / 250.

    #-----------------------------
    # for bi-linear stress-strain-diagram of the concrete (EC2)
    #-----------------------------

    sig_c_mfn = Property(depends_on = '+input')
    @cached_property
    def _get_sig_c_mfn(self):
        xdata = array([0., 0.00175, 0.0035])
        ydata = array([0., self.f_ck, self.f_ck])
        return MFnLineArray(xdata = xdata, ydata = ydata)

#    #-----------------------------
#    # for quadratic stress-strain-diagram of the concrete
#    #-----------------------------
#
#    sig_c_mfn = Property( depends_on = '+input' )
#    @cached_property
#    def _get_sig_c_mfn( self ):
#        xdata = array( [0., 0.00135, 0.0035] )
#        ydata = array( [0., self.f_ck, self.f_ck] )
#        return MFnLineArray( xdata = xdata, ydata = ydata )

    def get_sig_c(self, eps_c):
        sig_c = self.sig_c_mfn.get_value(eps_c)
        return sig_c

    sig_c_mfn_vect = Property(depends_on = '+input')
    @cached_property
    def _get_sig_c_mfn_vect(self):
        return frompyfunc( self.sig_c_mfn.get_value, 1, 1 )

    get_sig_c_vectorized = frompyfunc( get_sig_c, 1, 1 )

#    def get_a( self, u ):
#        x, f_t_i_arr = self.get_f_t_i_arr( u )
#        a = self.k * x / 2.
#        return a

    # number of subdivisions of the compressive zone
    #
    n_c = float(20)

    x_frac_i = Property(Array)
    @cached_property
    def _get_x_frac_i(self):
        '''subdivide the compression zone 'x' in 'n_c' sub-areas;
        'x_frac_i' giving the fraction of each distance of the sub-area from the upper surface 
        with respect to the compressive zone 'x'
        '''
        print 'x_frac_i', arange( self.n_c ) / self.n_c + 1. / ( 2. * self.n_c )
        return arange(self.n_c) / self.n_c + 1. / (2. * self.n_c)


    # iteration counter:
    #
    n = 1

    def get_lack_of_fit(self, u, M, N ):
        '''Return the difference between 
        N_c (=compressive force of the compressive zone of the concrete) 
        N_t (=total tensile force of the reinforcement layers)

        NOTE: eps_t (=tensile strain at the bottom [MPa]) is the search parameter
        to be found iteratively!
        '''
#        print '\n'
#        print '------------- iteration: %g ----------------------------' % ( self.n )

        x, f_t_i_arr = self.get_f_t_i_arr( u )

        # height of the cross section
        #
        thickness = self.thickness
#        print 'thickness', thickness

        z_t_i_arr = self.z_t_i_arr
#        print 'z_t_i_arr', z_t_i_arr

        # total tensile force of all layers of the composite tensile zone [kN]:
        # (characteristic value)
        #
        N_tk = sum( f_t_i_arr )
        # print 'N_tk', N_tk

        # total tensile force of all layers of the composite tensile zone [kN]:
        # (design value)
        #
#        N_td = N_tk / self.gamma_tex * self.beta
#        print 'N_td', N_td

#        k_exact = ( 1.74 * self.eps_c / 4.56 - ( self.eps_c / 4.56 ) ** 2 / ( 1 - 0.12 * self.eps_c / 4.56 ) )

#        # distance [m] of the resulting compressive 
#        # force from the top, i.e. a = k * x / 2
#        #
#        a = self.k * x / 2.
#        # print 'a', a
#
#        # total compressive force of the composite compressive zone [kN]:
#        # (characteristic value)
#        #
#        N_ck = 2.0 * a * self.width * self.chi * self.f_ck * 1000.

        # compressive strain in the compression zone 'x' in each sub-area ('A_c' divided in 'n_c' parts)
        #
        eps_c_i_arr = self.x_frac_i * self.eps_c
#        print 'eps_c_i_arr', eps_c_i_arr

        # @todo: get vectorized version running: 
#        sig_c_i_arr = self.sig_c_mfn_vect( eps_c_i_arr )
        sig_c_i_arr = array([self.get_sig_c(eps_c_i) for eps_c_i in eps_c_i_arr])
        
#        print 'sig_c_i_arr', sig_c_i_arr
        f_c_i_arr = sig_c_i_arr * self.width * self.x_frac_i[0] * 2. * x * 1000.

        z_c_i_arr = x * self.x_frac_i[::-1]
#        print 'z_c_i_arr', z_c_i_arr

        N_ck = sum( f_c_i_arr )

#        # total compressive force of the composite compressive zone [kN]:
#        # (design value)
#        #
#        N_cd = x * self.width * self.chi * self.f_cd * 1000.
#        print 'N_cd', N_cd

        # absolute error (equilibrium of sum N = 0):
        #
        N_external = N
        N_internal = -N_ck + N_tk
        d_N = N_internal - N_external

#        print 'd_N', d_N

        # resistance moment of one reinforced composite layer [kNm]:
        # (characteristic value)
        #
        M_tk = dot( f_t_i_arr, z_t_i_arr )
        # print 'M_tk', M_tk

#        M_ck = -a * N_ck
        M_ck = dot( f_c_i_arr, z_c_i_arr )

        M_internal = M_tk + M_ck

        M_external = M + N_external * thickness / 2.0

        d_M = M_internal - M_external
#        print 'd_M', d_M

        self.n += 1
#        print 'n', self.n

        return array([ d_N, d_M ], dtype = float)

    # iteration tries (up to now one try)
    # @todo: try different starting vectors 'u0' :
    #
    m = 0
    
    def fit_response(self, M, N, u0 = [ 0.010, 0.0033 ]):
#                      elem_no = 0, mx = 0.0, my = 0.0, mxy = 0.0, nx = 0.0, ny = 0.0, nxy = 0.0, \
#                      sig1_up = 0, sig1_lo_sig_up = 0, sig1_lo = 0, sig1_up_sig_lo = 0, ):
        '''iterate 'eps_t' such that the lack of fit between the calculated
        normal forces in the tensile reinforcement and the compressive zone (concrete)
        is smaller then 'xtol' defined in function 'brentq'.
        NOTE: the method 'get_lack_of_fit' returns the relative error.
        '''
#        self.m += 1
#        print '--- fit_response called --- %g' % ( self.m )

#        print self.thickness
#        print self.width

        thickness = self.thickness

        W = thickness ** 2 * self.width / 6.0
        A = thickness * self.width

        sig_bending = M / W / 1000.0
        sig_normal = N / A / 1000.0

        sig_plus = sig_normal + sig_bending
        sig_minus = sig_normal - sig_bending
        print 'M', M
        print 'N', N
#        print 'W', W
#        print 'A', A
#        print 'M/W', sig_bending
#        print 'N/A', sig_normal
        print 'thickness', thickness
        print 'self.width', self.width

#        print 'sig_plus', sig_plus
#        print 'sig_minus', sig_minus


        if sig_plus * sig_minus < 0.0:
            # bending

            # use scipy-functionality to get the iterated value of 'eps_t'
            # NOTE: 'get_lack_of_fit' must have a sign change as a requirement
            # for the function call 'brentq' to work property. 

            # The method brentq has optional arguments such as
            #   'xtol'    - absolut error (default value = 1.0e-12)
            #   'rtol'    - relative error (not supported at the time)
            #   'maxiter' - maximum numbers of iterations used
            #
            xtol = 1.0e-5

            # default value as defined in 'calib_config'
            #
            u0 = self.u0
            
            #----------------
            # @todo: how can the rupture strain in the bending test be estimated realistically?
            # in which boundaries shall brentq search for a solution? (5*eps_u)?
            #----------------
            #
            # @todo: find a starting estimate for 'fsolve'
            # depending on the given values of 'M' and 'N'
            #
#            E_comp = 30000. # MPa
#            eps_t_estimate = abs(sig_plus) / E_comp
#            eps_c_estimate = abs(sig_minus) / E_comp
#            u0 = [eps_t_estimate, eps_c_estimate]
#            print 'u0', u0

            # use 'fsolve' to find the solution vector 'u' in order to minimize
            # the 'lack_of_fit' within the given tolerance 'xtol'
            #
            u_sol = fsolve(self.get_lack_of_fit, u0, args = (M, N), xtol = xtol)
#            print 'u_sol', u_sol

            # @todo: check if 'brenth' gives better fitting results; faster? 
    #            phi_new = brenth( self.get_lack_of_fit, 0., eps_t )

        else:

            raise ValueError, 'pure tension or pure bending'# with\n input elem_num = %d,\n %g, %g, %g, %g, %g, %g, %g, %g, %g, %g' % ( elem_no, mx, my, mxy, nx, ny, nxy, sig1_up, sig1_lo_sig_up, sig1_lo, sig1_up_sig_lo )

#        print 'u_sol', u_sol
#        print 'u_sol.shape', u_sol.shape
#        print 'type(u_sol)', type( u_sol )
#        return u_sol[0], u_sol[1]
        return u_sol

    calib_config = Trait('eps_t_E_yarn',
                          {'eps_t_E_yarn' : ('layer_response_eps_t_E_yarn',
                                              array([ 0.010, 50000.0 ])),
                           'eps_t_eps_c' : ('layer_response_eps_t_eps_c',
                                             array([ 0.010, 0.0033 ])) },
                         modified = True)

    layer_response = Property(depends_on = 'calib_config')
    @cached_property
    def _get_layer_response(self):
        return getattr(self, self.calib_config_[0])

    u0 = Property(Array(float), depends_on = 'calib_config')
    @cached_property
    def _get_u0(self):
        return self.calib_config_[1]

    def get_sig_max( self, u ):
        sig_max = max(self.get_sig_comp_i_arr( u ))
        print 'sig_max', sig_max
        return sig_max

if __name__ == '__main__':

    import pylab as p

    #------------------------------
    # define input params
    #------------------------------
    #
    thickness_unreinf = 0.0
    N = 0.

    # measured value in bending test
    #
    M = 3.49

    # bending moment corresponds to a 
    # line moment of the following value in [kNm/m]
    #
#    M = 5*3.49

    #------------------------------------------------
    # get 'E_yarn' and 'eps_t' for given 'eps_c'
    #------------------------------------------------
    #
    print '\n'
    print 'setup SigFlCalib'
    print '\n'
    sig_fl_calib = SigFlCalib( calib_config = 'eps_t_E_yarn',# concrete strength after 9 days
                               #
                               f_ck = 49.9,

                               # measured strain at bending test rupture (0-dir)
                               #
                               eps_c = 3.3 / 1000.,

                               # values for experiment beam with width = 0.20 m
                               #
                               width = 0.20,
                               n_roving = 23,

#                               # values per m
#                               #
#                               width = 1.0,
#                               n_roving = 120,

                              )

    #------------------------------------------------
    # calibration of effective crack bridge law:
    #------------------------------------------------
    #
#    sig_fl_calib.calib_config = 'eps_t_E_yarn'
    sig_fl_calib.set(calib_config = 'eps_t_E_yarn')
    
    eps_t, E_yarn = sig_fl_calib.fit_response( M, N )
    print 'E_yarn', E_yarn
    eps_c = sig_fl_calib.eps_c
    print 'eps_t', eps_t
    print 'eps_c', eps_c
    print 'max_sig', sig_fl_calib.get_sig_max([ eps_t, eps_c ] )

    #------------------------------------------------
    # get 'eps_c', 'esp_t' for given/calibrated 'E_yarn' 
    #------------------------------------------------
    
#    E_yarn = 84384.2115269
#    N = 10
#    M = 30
    print '\n'
    print 'set E_yarn to %g' % (E_yarn)
    print '\n'
    sig_fl_calib.set(E_yarn = E_yarn,
                     calib_config = 'eps_t_eps_c')

    u0 = [0.003, 0.01]
    print 'starting with u0 = [%g, %g]' % (u0[0], u0[1])

    eps_t, eps_c = sig_fl_calib.fit_response( M, N, u0)
    print 'eps_t', eps_t
    print 'eps_c', eps_c
    print 'max_sig', sig_fl_calib.get_sig_max([ eps_t, eps_c ] )

    #------------------------------------------------
    # plot response
    #------------------------------------------------
    #
    layer_arr = arange( sig_fl_calib.n_layers )
    sig_comp_i_arr = sig_fl_calib.get_sig_comp_i_arr([eps_t, eps_c] )
    p.bar(layer_arr, sig_comp_i_arr, 0.2)
#    ax2 = p.twinx()
#    ax2.plot(layer_arr, sig_fl_calib.eps_t_i_arr)

#    print 'eps_t_i_arr', sig_fl_calib.eps_t_i_arr
#    p.plot( layer_arr, sig_fl_calib.eps_t_i_arr )

    p.show()

