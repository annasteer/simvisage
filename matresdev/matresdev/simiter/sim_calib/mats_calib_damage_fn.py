#-------------------------------------------------------------------------------
#
# Copyright (c) 2009, IMB, RWTH Aachen.
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD
# license included in simvisage/LICENSE.txt and may be redistributed only
# under the conditions described in the aforementioned license.  The license
# is also available online at http://www.simvisage.com/licenses/BSD.txt
#
# Thanks for using Simvisage open source!
#
# Created on May 29, 2009 by: rch

from etsproxy.traits.api import \
    Float, Instance, Array, Int, Property, cached_property, on_trait_change, Bool, \
    HasTraits, File, Event

from etsproxy.traits.ui.api import \
    View, Item, FileEditor, HSplit, Group, VSplit, \
    Handler

from etsproxy.traits.ui.menu import \
    Action, CloseAction, HelpAction, Menu, \
    MenuBar, NoButtons, Separator, ToolBar, CancelButton, OKButton

from etsproxy.pyface.api import ImageResource

from ibvpy.mats.mats_explore import MATSExplore
from ibvpy.mats.mats2D.mats2D_explore import MATS2DExplore
from numpy import copy, array, hstack, loadtxt, savetxt
from mathkit.mfn import MFnLineArray

from scipy.optimize import brentq, newton, fsolve, brenth
from os.path import join
from ibvpy.core.tloop import TLoop, TLine
from ibvpy.core.scontext import SContext
from ibvpy.core.tstepper import TStepper

from promod.exdb.ex_run import ExRun

data_file_editor = FileEditor(filter = ['*.DAT'])

from util.traits.editors.mpl_figure_editor import MPLFigureEditor
from matplotlib.figure import Figure
import pickle
from copy import copy

from matresdev.db.simdb import SimDB
simdb = SimDB()


# ---------------------------------------------------
# Calibration controller
# ---------------------------------------------------

class MATSCalibDamageFnController(Handler):
    '''Handle the dynamic interaction with the calibrator.
    '''

    #---------------------------------------------------------------------------
    # Public Controller interface
    #---------------------------------------------------------------------------
    def run_calibration(self, ui_info):

        calibrator = ui_info.object

        calibrator.init()
        fit_response = calibrator.fit_response()

#       @todo: delete
#       this code was here for saving the damage function in a file - however currently the values
#       should be automatically stored in the fit_response method
#        ex_run = calibrator.ex_run_view.model
#        
#        # Construct the name of the material combination to store the
#        # material parameters with.
#        #
#        file_name = join( simdb.matdata_dir, ex_run.ex_type.textile_cross_section_key + '.mats' )
#        file = open( file_name, 'w' )
#
#        import pickle
#        mats_eval = calibrator.dim.mats_eval
#        pickle.dump( mats_eval.phi_fn.mfn, file )
#        file.close()

# ---------------------------------------------------
# Calibrator of the damage function from uniaxial test: 
# ---------------------------------------------------

class MATSCalibDamageFn(MATSExplore):
    '''
    Fitting algorithm for the damage function of the 
    quasi-ductile anisotropic material model.
    
    The algorithm uses the TLoop instance to proceed step 
    by step with the computation. The value of the damage function 
    for the time step t_n is identified iteratively by adjusting
    the values and evaluating the corresponding equilibrated stresses.
    
    The control parameters of the algorithm are:
    
    @param step_size: time step for fitting the damage parameter.
    @param tmax: end time for fitting, it might be also be set implicitly 
    for integrity = 1 - full damage of the material.
    '''

    # default settings are overloaded with settings specified in 'ec_config'

    max_load = Property(Float)
    def _get_max_load(self):
        return self.mfn_line_array_target.xdata[-1]

    n_steps = Int(1)

    log = Bool(False)

    # TLine parameter
    #
    KMAX = Int
    tolerance = Float
    RESETMAX = Float

    step_size = Property(Float)
    def _get_step_size(self):
        return self.max_load / self.n_steps


    def run_through(self):
        '''Run the computation without fitting from the start to the end
        '''
        self.tloop.tline.max = self.tmax
        self.tloop.tline.step = self.step_size
        self.tloop.eval()
        print 'ending time', self.tloop.t_n1
        # show the response

    def run_step_by_step(self):
        '''Run the computation step by step from the start to the end
        '''
        n_steps = int(self.tmax / self.step_size)
        self.tloop.tline.step = self.step_size
        current_time = 0.
        tmax = 0.
        for i in range(n_steps):
            print 'STEP', i
            self.run_one_step()

    def run_trial_step(self):
        '''Run the computation one step starting from the
        current time t_n to iterate the value for phi_new 
        which gives a fit with macroscopic stress curve.
        NOTE: The trial step does not update 'U_n' or 't_n'!
        '''
        if self.log:
            print '--------- run trial step: --------- '
        if len(self.tloop.U_n) == 0:
            current_U_n = self.tloop.tstepper.new_cntl_var()
            print 'U_n = None: tloop.tstepper.new_cntl_var()', self.tloop.tstepper.new_cntl_var()
        else:
            current_U_n = self.tloop.U_n[:]
        current_time = self.tloop.t_n
        self.run_one_step()

        # reset the current time back
        self.tloop.t_n = current_time
        self.tloop.U_n[:] = current_U_n[:]
        if self.log:
            print '--------- end of trial step --------- '

        self.tloop.tstepper.sctx.update_state_on = False

    def run_one_step(self):
        '''Run the computation one step starting from the
        current time t_n with the iterated value for phi_new
        in order to update TLoop and save the new phi value in
        the array ydata of PhiFnGeneral
        NOTE: The calculated step does update 'U_n' or 't_n'!
        '''
        self.tloop.tline.step = self.step_size
        current_time = self.tloop.t_n
        tmax = current_time + self.step_size
        self.tloop.tline.max = tmax
        self.tloop.eval()
        self.update_e_max_value_new = True

    #--------------------------------------------------
    # Data source for calibration within simdb
    #--------------------------------------------------

    ex_run = Instance(ExRun)

    composite_tensile_test = Property
    def _get_composite_tensile_test(self):
        return self.ex_run.ex_type

    composite_cross_section = Property
    def _get_composite_cross_section(self):
        return self.composite_tensile_test.ccs

    def get_target_data_exdb_tensile_test(self):
        '''Use the data from the ExDB
        '''
        ctt = self.composite_tensile_test
        return ctt.eps_smooth, ctt.sig_c_smooth

    #--------------------------------------------------
    # interpolation function for fitting data:
    #--------------------------------------------------
    mfn_line_array_target = Property(Instance(MFnLineArray),
                                      depends_on = 'ex_run')
    @cached_property
    def _get_mfn_line_array_target(self):
        xdata, ydata = self.get_target_data_exdb_tensile_test()
        return MFnLineArray(xdata = xdata, ydata = ydata)

    fitted_phi_fn = Instance(MFnLineArray)

    #---------------------------------------------------------------
    # PLOT OBJECT
    #-------------------------------------------------------------------
    figure = Instance(Figure)
    def _figure_default(self):
        figure = Figure(facecolor = 'white')
        figure.add_axes([0.12, 0.13, 0.85, 0.74])
        return figure

    data_changed = Event

    def init(self):
        #--------------------------------------------------
        # for fitting use 'General'-function for 'phi_fn': 
        #--------------------------------------------------
        # The value pair for the piecewise linear definition
        # of 'phi_fn' value consists of current strain and the
        # iterated 'phi_value'. The microplanes with a lower
        # microplane strain level use an interpolated value 
        # for 'phi' 
        self.fitted_phi_fn = self.dim.mats_eval.phi_fn.mfn
        self.fitted_phi_fn.xdata = [0]
        self.fitted_phi_fn.ydata = [1]
        self.fitted_phi_fn.data_changed = True
        # initialize TLoop parameters:
        self.tloop.setup()
        self.tloop.tstepper.sctx.mats_state_array[:] = 0.0
        self.tloop.U_n[:] = 0.0
        self.tloop.rtrace_mngr.clear()
        self.tloop.verbose_iteration = False
        self.tloop.verbose_load_step = False
        self.tloop.verbose_time = False
        # set TLine parameters
        self.tloop.tline.KMAX = self.KMAX
        self.tloop.tline.tolerance = self.tolerance
        self.tloop.tline.RESETMAX = self.RESETMAX



    def get_lack_of_fit(self, phi_trial):
        '''Return the difference between the macroscopic stress calculated
        based on the value of phi_trial (damage at the next step) and the
        macroscopic stress defined as target data (=fitting curve)
        '''
        if self.log:
            print '\n'
            print "#'get_lack_of_fit' for the trial value # START"
            print '    phi_trial    = ', phi_trial

        # value of the principle macroscopic strain corresponds to control variable
        current_time = self.tloop.t_n

        if self.log:
            print '    current_time = ', current_time
            print '    step_size    = ', self.step_size

        # ------------------------------------                
        # add new pair in fitted_phi_fn 
        # ------------------------------------                
        # consisting of 'e_max_value_new' and 'phi_trial'
        x = hstack([ self.fitted_phi_fn.xdata[:], current_time + self.step_size ])
        y = hstack([ self.fitted_phi_fn.ydata[:], phi_trial ])
        self.fitted_phi_fn.set(xdata = x, ydata = y)
        self.fitted_phi_fn.data_changed = True

        # ------------------------------------                
        # get state array before trial:
        # ------------------------------------                
        mats_state_array_old = copy(self.tloop.tstepper.sctx.mats_state_array)

        # ------------------------------------                
        # run trial step: 
        # ------------------------------------                
        if self.log:
            print '    reset current_U_n   =', self.tloop.U_n
            print 'CURRENT PHI', self.dim.mats_eval.phi_fn.mfn.ydata
        # try the next equilibrium
        self.run_trial_step()

        # ------------------------------------                
        # reset mats_state_array:
        # ------------------------------------                
        # Note: the material state array (i.e. the maximum microstrains) are 
        # updated within the iterations of each trial step, therefore a reset
        # is necessary in order to start each trial step with the same state variables  
        self.tloop.tstepper.sctx.mats_state_array[:] = mats_state_array_old[:]
        if self.log:
            print '    reset state array'

        # ------------------------------------                
        # remove trial value in fitted_phi_fn 
        # ------------------------------------                
        x = self.fitted_phi_fn.xdata[:-1]
        y = self.fitted_phi_fn.ydata[:-1]
        self.fitted_phi_fn.set(xdata = x, ydata = y)
        self.fitted_phi_fn.data_changed = True

        # ------------------------------------                
        # get the lack of fit
        # ------------------------------------                
        # get calculated value for 'sig_app' based on the current value of 'phi_trial':
        # and evaluate the difference between the obtained stress and the measured response
        self.tloop.rtrace_mngr.rtrace_bound_list[0].redraw()
        sig_app_trial = self.tloop.rtrace_mngr.rtrace_bound_list[0].trace.ydata[-1]
        # get corresponding value from the target data:
        sig_app_target = self.mfn_line_array_target.get_value(current_time + self.step_size)
        # absolut error:
        lack_of_fit_absolut = sig_app_trial - sig_app_target
        # relative error:
        lack_of_fit_relative = lack_of_fit_absolut / sig_app_target

        if self.log:
            print '    sig_app_trial ', sig_app_trial
            print '    sig_app_target', sig_app_target
            print '    lack_of_fit_absolute  ', lack_of_fit_absolut
            print '    lack_of_fit_relative  ', lack_of_fit_relative
            print '# get_lack_of_fit # END '

        return lack_of_fit_relative

    def fit_response(self):
        '''iterate phi_trial in each incremental step such that the
        lack of fit between the calculated stress and the target
        curve is smaller then xtol defined in function 'brentq'.
        NOTE: the method 'get_lack_of_fit' returns the relative error.
        '''

        self.tloop.reset()

        phi_old = 1.0

        # map the array dimensions to the plot axes
        #
        figure = self.figure

        axes = figure.axes[0]

        print 'n_steps', self.n_steps
        for n in range(self.n_steps):

            axes.clear()

            phi_new = phi_old

            # use scipy-functionality to get the iterated value of phi_new
            # If the trial value calculated with phi_trial = phi_old
            # is smaller then target value get_lack_of_fit has no sign change
            # for phi_trial = phi_old and phi_trial = 0. which is a requirement
            # for the function call 'brentq'. In this case the old value
            # for phi_trial is used and tloop moves on one step 
            try:
                # The method brentq has optional arguments such as
                #   'xtol'    - absolut error (default value = 1.0e-12)
                #   'rtol'    - relative error (not supported at the time)
                #   'maxiter' - maximum numbers of iterations used
                #
                # Here xtol is used to specify the allowed RELATIVE error!
                # therefore the relative lack of fit is returned in 
                # method 'get_lack_of_fit' 
                _xtol = 1.0e-6
                phi_new = brentq(self.get_lack_of_fit, 0., phi_old, xtol = _xtol)
                # @todo: check if 'brenth' gives better fitting results; faster? 
#                phi_new = brenth( self.get_lack_of_fit, 0., phi_old )
            except ValueError:

                lof_0 = self.get_lack_of_fit(0.)
                lof_phi_old = self.get_lack_of_fit(phi_old)
                if self.log:
                    print 'No sign change between get_lack_of_fit(phi_old) = ', lof_phi_old, ' and '
                    print 'get_lack_of_fit(0.) = ', lof_0
                    print 'Use old value for phi_trial. phi_old = ', phi_old
                else:
                    print '(!)',

            # current time corresponds to the current strain applied
            current_time = self.tloop.t_n

            # replace old 'phi_value' with iterated value:
            phi_old = phi_new

            # get mats_state_array:
            mats_state_array = copy(self.tloop.tstepper.sctx.mats_state_array)

            # update phi_data:
            x = hstack([ self.fitted_phi_fn.xdata[:], current_time + self.step_size  ])
            y = hstack([ self.fitted_phi_fn.ydata[:], phi_new             ])

            axes.plot(x, y, color = 'blue', linewidth = 2)
            self.data_changed = True

            self.fitted_phi_fn.set(xdata = x, ydata = y)
            self.fitted_phi_fn.data_changed = True

            # run one step with the iterated value for phi in order to
            # update the state array and to move forward one step:
            if self.log:
                print '\n'
                print '### run_one_step ###'
                print '### step', n   , '###'
                print '### current time:', current_time
            self.run_one_step()
            print '#',

        self.fitted_phi_fn.changed = True
        mats_eval = self.dim.mats_eval.__class__.__name__
        ctt_key = str(self.composite_tensile_test.key)
        self.composite_cross_section.set_param(mats_eval, ctt_key,
                                               copy(self.fitted_phi_fn))

    #-----------------------------------------------------------------------------------------
    # User interaction
    #-----------------------------------------------------------------------------------------
    toolbar = ToolBar(
                  Action(name = "Run Calibration",
                         tooltip = 'Run damage function calibration for the current parameters',
                         image = ImageResource('kt-start'),
                         action = "run_calibration"),
                  image_size = (22, 22),
                  show_tool_names = False,
                  show_divider = True,
                  name = 'calibration_toolbar')

    traits_view = View(HSplit(
                            Item('ex_run@',
                                    show_label = False),
                            VSplit(
                               Item('dim@',
                                    id = 'mats_calib_damage_fn.run.split',
                                    dock = 'tab',
                                    resizable = True,
                                    label = 'experiment run',
                                    show_label = False),
                                    id = 'mats_calib_damage_fn.mode_plot_data.vsplit',
                                    dock = 'tab',
                                ),
                            VSplit(
                                Group(
                                      Item('figure', editor = MPLFigureEditor(),
                                         resizable = True, show_label = False),
                                    id = 'mats_calib_damage_fn.plot_sheet',
                                    label = 'fitted damage function',
                                    dock = 'tab',
                                    ),
                                    id = 'mats_calib_damage_fn.plot.vsplit',
                                    dock = 'tab',
                                   ),
                                    id = 'mats_calib_damage_fn.hsplit',
                                    dock = 'tab',
                                ),
#                        menubar = self.default_menubar(),
                        resizable = True,
                        toolbar = toolbar,
                        handler = MATSCalibDamageFnController(),
                        title = 'Simvisage: damage function calibration',
                        id = 'mats_calib_damage_fn',
                        dock = 'tab',
                        buttons = [ OKButton, CancelButton ],
                        height = 0.8,
                        width = 0.8)


def run():
    #--------------------------------------------------------------------------------
    # Example using the mats2d_explore 
    #--------------------------------------------------------------------------------
    from ibvpy.mats.mats2D.mats2D_explore import MATS2DExplore
    from ibvpy.mats.mats2D.mats2D_rtrace_cylinder import MATS2DRTraceCylinder

    from ibvpy.mats.mats2D.mats2D_cmdm.mats2D_cmdm_rtrace_Gf_mic import \
        MATS2DMicroplaneDamageTraceGfmic, \
        MATS2DMicroplaneDamageTraceEtmic, MATS2DMicroplaneDamageTraceUtmic

    from ibvpy.mats.mats2D.mats2D_cmdm.mats2D_cmdm_rtrace_Gf_mac import \
        MATS2DMicroplaneDamageTraceGfmac, \
        MATS2DMicroplaneDamageTraceEtmac, MATS2DMicroplaneDamageTraceUtmac

    from ibvpy.mats.mats2D.mats2D_cmdm.mats2D_cmdm import \
        MATS2DMicroplaneDamage, MATS1DMicroplaneDamage, \
        PhiFnGeneral, PhiFnStrainHardening

    from ibvpy.api import RTraceGraph, RTraceArraySnapshot

    from mathkit.mfn import MFnLineArray
    from numpy import array, hstack

    from ibvpy.mats.mats2D.mats2D_explorer_bcond import BCDofProportional
    from os.path import join

    ec = {
          # overload the default configuration
          'bcond_list'  : [ BCDofProportional(max_strain = 1.0, alpha_rad = 0.0) ],
          'rtrace_list' : [
               RTraceGraph(name = 'stress - strain',
                           var_x = 'eps_app', idx_x = 0,
                           var_y = 'sig_app', idx_y = 0,
                           update_on = 'iteration'),
                        ],
          }

    mats_eval = MATS2DMicroplaneDamage(
                                    n_mp = 30,
    #mats_eval = MATS1DMicroplaneDamage(
                                    elastic_debug = False,
                                    stress_state = 'plane_stress',
                                    symmetrization = 'sum-type',
                                    model_version = 'compliance',
                                    phi_fn = PhiFnGeneral,
                                    )

    print 'normals', mats_eval._MPN
    print 'weights', mats_eval._MPW

    fitter = MATSCalibDamageFn(n_steps = 50,
                                KMAX = 200,
                                tolerance = 5e-4, #0.01,
                                RESETMAX = 0,
                                dim = MATS2DExplore(
                                                    mats_eval = mats_eval,
                                                    explorer_config = ec,
                                                    ),
                                log = False
                                )

    #-------------------------------------------
    # run fitter for entire available test data:
    #-------------------------------------------

    calibrate_all = False

    if calibrate_all:
        from promod.exdb.ex_run_table import \
            ExRunClassExt
        from promod.exdb.ex_composite_tensile_test import \
            ExCompositeTensileTest
        ex = ExRunClassExt(klass = ExCompositeTensileTest)
        for ex_run in ex.ex_run_list:
            if ex_run.ready_for_calibration:
                print 'FITTING', ex_run.ex_type.key
                # 'E_c' of each test is different, therefore 'mats_eval' 
                # needs to be defined for each test separately. 
                #
                E_c = ex_run.ex_type.E_c
                nu = ex_run.ex_type.ccs.concrete_mixture_ref.nu

                # run calibration
                #
                fitter.ex_run = ex_run
                fitter.dim.mats_eval.E = E_c
                fitter.dim.mats_eval.nu = nu
                fitter.init()
                fitter.fit_response()

    else:

        test_file = join(simdb.exdata_dir,
                              'tensile_tests',
#                              'TT-10a',
#                              'TT11-10a-average.DAT' )
                              '2012-01-09_TT-12c-6cm-TU-SH1',
                              'TT-12c-6cm-TU-SH1F-V3.DAT')

        ex_run = ExRun(data_file = test_file)

        # get the composite E-modulus and Poisson's ratio as stored
        # in the experiment data base and use this in mats_eval.
        #
        E_c = ex_run.ex_type.E_c
        nu = ex_run.ex_type.ccs.concrete_mixture_ref.nu

        fitter.ex_run = ex_run
        fitter.dim.mats_eval.E = E_c
        fitter.dim.mats_eval.nu = nu
        fitter.init()
        ctt = fitter.composite_tensile_test
        fitter.fit_response()

    return

    #---------------------------
    # basic testing of fitter methods:
    #---------------------------

    # set to True for basic testing of the methods:
    basic_tests = False

    if basic_tests:
        fitter.run_through()
        #    fitter.tloop.rtrace_mngr.rtrace_bound_list[0].configure_traits()
        fitter.tloop.rtrace_mngr.rtrace_bound_list[0].redraw()
        last_strain_run_through = fitter.tloop.rtrace_mngr.rtrace_bound_list[0].trace.xdata[:]
        last_stress_run_through = fitter.tloop.rtrace_mngr.rtrace_bound_list[0].trace.ydata[:]
        print 'last strain (run-through) value' , last_strain_run_through
        print 'last stress (run-through) value' , last_stress_run_through

        fitter.tloop.reset()
        fitter.run_step_by_step()
        #fitter.tloop.rtrace_mngr.rtrace_bound_list[0].configure_traits()
        fitter.tloop.rtrace_mngr.rtrace_bound_list[0].redraw()
        last_strain_step_by_step = fitter.tloop.rtrace_mngr.rtrace_bound_list[0].trace.xdata[:]
        last_stress_step_by_step = fitter.tloop.rtrace_mngr.rtrace_bound_list[0].trace.ydata[:]
        print 'last stress (step-by-step) value', last_stress_step_by_step

        fitter.run_trial_step()
        fitter.run_trial_step()
        fitter.tloop.rtrace_mngr.rtrace_bound_list[0].redraw()
        strain_after_trial_steps = fitter.tloop.rtrace_mngr.rtrace_bound_list[0].trace.xdata[:]
        stress_after_trial_steps = fitter.tloop.rtrace_mngr.rtrace_bound_list[0].trace.ydata[:]
        print 'stress after trial', stress_after_trial_steps

        fitter.init()
        #fitter.mats2D_eval.configure_traits()
        lof = fitter.get_lack_of_fit(1.0)
        print '1', lof
        lof = fitter.get_lack_of_fit(0.9)
        print '2', lof

        #fitter.tloop.rtrace_mngr.configure_traits()
        fitter.run_trial_step()

    else:
        from ibvpy.plugins.ibvpy_app import IBVPyApp
        ibvpy_app = IBVPyApp(ibv_resource = fitter)
        ibvpy_app.main()

if __name__ == '__main__':
    run()
