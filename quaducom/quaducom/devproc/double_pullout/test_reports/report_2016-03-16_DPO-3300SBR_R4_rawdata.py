'''
Created on Mar 17, 2016

'''

from matresdev.db.simdb import SimDB
simdb = SimDB()
from matresdev.db.exdb import ExRun

import os
import numpy as np
import pylab as p
params = {'legend.fontsize': 10,
          # 'legend.linewidth': 2
          }
p.rcParams.update(params)

test_files = [       
    'DPO-10cm-0-3300SBR-V1_R4.DAT',
    'DPO-10cm-0-3300SBR-V2_R4.DAT',
    'DPO-10cm-0-3300SBR-V3_R4.DAT',         
    'DPO-20cm-0-3300SBR-V1_R4.DAT',
    'DPO-20cm-0-3300SBR-V2_R4.DAT',
    'DPO-20cm-0-3300SBR-V3_R4.DAT',         
    'DPO-30cm-0-3300SBR-V1_R4.DAT',
    'DPO-30cm-0-3300SBR-V2_R4.DAT',
    'DPO-30cm-0-3300SBR-V3_R4.DAT',
    'DPO-40cm-0-3300SBR-V1_R4.DAT',
    'DPO-40cm-0-3300SBR-V2_R4.DAT',
    'DPO-40cm-0-3300SBR-V3_R4.DAT',
    'DPO-50cm-0-3300SBR-V1_R4.DAT',
    'DPO-50cm-0-3300SBR-V2_R4.DAT',
    'DPO-50cm-0-3300SBR-V3_R4.DAT',
    'DPO-60cm-0-3300SBR-V1_R4.DAT',
    'DPO-60cm-0-3300SBR-V2_R4.DAT',
    'DPO-60cm-0-3300SBR-V3_R4.DAT',
    'DPO-70cm-0-3300SBR-V1_R4.DAT',
    'DPO-70cm-0-3300SBR-V2_R4.DAT',
    'DPO-70cm-0-3300SBR-V3_R4.DAT',
    ]

test_file_path = os.path.join(simdb.exdata_dir,
                              'double_pullout',
                              '2016-03-16_DPO-15mm-0-3300SBR_R4',
                              'raw_data')

e_list = [ExRun(data_file=os.path.join(test_file_path, test_file))
          for test_file in test_files]

color_list = [
    'r','r','r','g','g','g','b','b','b',
    'k','k','k','mediumturquoise','mediumturquoise','mediumturquoise','firebrick', 
    'firebrick','firebrick','darkblue','darkblue','darkblue'
    ]

linestyle_list = [
    '-',    '-',    '-',    '-',    '-',    '-',    '-',    '-',
    '-',    '-',    '-',    '-',    '-',    '-',    '-',    '-',
    '-',    '-',    '-',    '-',    '-',
    ]


n_roving_list = [
                 9,9,9,
                 8,8,8,
                 8,9,9,
                 8,9,9,
                 8,8,8,
                 9,9,9,
                 9,8,8,
                 ]
def plot_all():

    fig = p.figure(facecolor='white', figsize=(12, 9))
    fig.subplots_adjust(
        left=0.07, right=0.97, bottom=0.08, top=0.96, wspace=0.25, hspace=0.2)

    for idx, (e_run, n_r) in enumerate(zip(e_list, n_roving_list)):
        e = e_run.ex_type
        
        axes = p.subplot(111)

        w10_re = e.W10_re#[:e.max_stress_idx + 1] 
        w10_li = e.W10_li#[:e.max_stress_idx + 1]
        w10_vo = e.W10_vo#[:e.max_stress_idx + 1]
        
        w = ((w10_re + w10_li) / 2.0 + w10_vo) / 2.0
        
        axes.plot(w, e.Kraft / n_r, linewidth=1.5, linestyle=linestyle_list[idx], color=color_list[idx])
        #label = test_files[idx].split('.')[0]
        #e._plot_force_displacement_asc(axes)
        axes.grid()
        axes.set_xlabel('$\Delta$ w [mm]')
        axes.set_ylabel('Kraft je Roving [kN]')

    axes.legend(loc=2)
    axes.axis([0., 15, 0., 2.5])

if __name__ == '__main__':
    plot_all()
    p.show()
