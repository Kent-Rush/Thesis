from numpy import *
from numpy.linalg import *
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.integrate import ode
from scipy.spatial.transform import Rotation as R
#import pymap3d as pm
from sgp4.earth_gravity import wgs84
from sgp4.io import twoline2rv
import datetime
import sys


sys.path.insert(0, '../../Aero_Funcs')

import read_lightcurve_data as rlc
import simulation_config as config
import Aero_Funcs as AF
import Aero_Plots as AP
import Controls_Funcs as CF
import Reflection_Funcs as RF



TRUTH = config.TRUTH()
VARIABLES = config.VARIABLES()

ALBEDO = TRUTH.ALBEDO
INERTIA = TRUTH.INERTIA
MEASUREMENT_VARIANCE = TRUTH.MEASUREMENT_VARIANCE

ROTATION = VARIABLES.ROTATION
DT = VARIABLES.DT
PASS = VARIABLES.PASS
LAT = VARIABLES.LATITUDE
LON = VARIABLES.LONGITUDE
ALT = VARIABLES.ALTITUDE
R_SPECULAR = VARIABLES.R_SPECULAR
R_DIFFUSION = VARIABLES.R_DIFFUSION
N_PHONG = VARIABLES.N_PHONG
C_SUN = VARIABLES.C_SUN

PLATE_SC = RF.Premade_Spacecraft().BOX_WING

def main():

    angular_velocity0 = array([0,0.1,0])
    # eta0 = 1
    # eps0 = array([0,0,0])

    q0 = array([1,2,3,4])/norm([1,2,3,4])
    eta0 = q0[3]
    eps0 = q0[0:3]

    eulers = array([0,0,0])

    state0 = hstack([eta0, eps0, angular_velocity0])


    #propagate rotation
    solver = ode(config.propagate_quats)
    solver.set_integrator('lsoda')
    solver.set_initial_value(state0, 0)
    solver.set_f_params(identity(3))

    newstate_rotation = []
    time = []
    tspan = 400
    while solver.successful() and solver.t < tspan:

        newstate_rotation.append(solver.y)
        time.append(solver.t)

        solver.integrate(solver.t + DT)
        loading_bar(solver.t/tspan, 'Simulating Rotation')

    newstate_rotation = vstack(newstate_rotation)
    time = hstack(time)


    #propagate orbit

    r_orbit = 6378 + 400
    r_site = 6378
    angle = arccos(r_site/r_orbit)
    pos0 = CF.Cz(-angle, degrees = False)@array([r_orbit,0,0])
    vel0 = CF.Cz(-angle, degrees = False)@array([0,sqrt(398600/r_orbit), 0])

    state0 = hstack([pos0, vel0])

    solver = ode(propagate_orbit)
    solver.set_integrator('lsoda')
    solver.set_initial_value(state0, 0)

    newstate_orbit = []
    tspan = 400
    while solver.successful() and solver.t < tspan:

        newstate_orbit.append(solver.y)

        solver.integrate(solver.t + DT)
        loading_bar(solver.t/tspan, 'Simulating Orbit')

    newstate_orbit = vstack(newstate_orbit)

    sc_gs = array([1,0,0])*r_site - newstate_orbit[:,0:3]
    attitudes = newstate_rotation[:,0:4]




    #Generate lightcurve
    lightcurve = states_to_lightcurve(time, sc_gs, attitudes, PLATE_SC, quats = True)

    plt.plot(time, lightcurve)
    plt.show()


    #Save Data

    # save('true_lightcurve', lightcurve)
    # save('true_states', newstate_rotation)
    # save('time', time)

    # sc_pos, tel_pos, sun_pos = get_positions(time, PASS)
    # save('sc_pos', sc_pos)
    # save('tel_pos', tel_pos)
    # save('sun_pos', sun_pos)

    # colors = []
    # for x, y in zip(sc_pos, sun_pos):
    #     if AF.shadow(x, y) == 0:
    #         colors.append('k')
    #     else:
    #         colors.append('b')


    # fig = plt.figure()
    # ax = Axes3D(fig)
    # AP.plot_earth(ax)
    # ax.scatter(sc_pos[:,0], sc_pos[:,1], sc_pos[:,2], c = colors)
    # AP.plot_orbit(ax, tel_pos)
    # AP.scale_plot(ax)


    # azimuth, elevation = AF.pass_az_el(tel_pos, sc_pos)

    # fig = plt.figure()
    # ax = fig.add_subplot(111, projection = 'polar')
    # #matplotlib takes azimuth in radians and elevation in degrees for some reason :/
    # ax.scatter(radians(azimuth), 90-elevation, c = colors)
    # ax.set_ylim([0,90])


    # plt.figure()
    # plt.plot(time, sc_posses)

    # plt.figure()
    # plt.plot(time, lightcurve, '.')
    # plt.show()


def propagate_orbit(t, state, mu = 398600):
    pos = state[0:3]
    vel = state[3:6]

    d_pos = vel
    d_vel = -pos*mu/norm(pos)**3

    return hstack([d_pos, d_vel])


def states_to_lightcurve(times, obs_vecs, attitudes, spacecraft_geometry, quats = False):

    lightcurve = []

    iters = len(times)
    count = 0
    for time, obs_vec, attitude in zip(times, obs_vecs, attitudes):

        #now = utc0 + datetime.timedelta(seconds = time)

        #sun_vec = AF.vect_earth_to_sun(now)
        sun_vec = array([0,1,0])

        if quats:
            eta = attitude[0]
            eps = attitude[1:4]
            dcm_body2eci = CF.quat2dcm(eta, eps)
        else:
            eulers = state[:3]
            dcm_body2eci = CF.euler2dcm(ROTATION, eulers)

        sun_vec_body = dcm_body2eci.T@sun_vec
        obs_vec_body = dcm_body2eci.T@obs_vec
        power = spacecraft_geometry.calc_reflected_power(obs_vec_body, sun_vec_body)

        lightcurve.append(power)

        count += 1
        loading_bar(count/iters, 'Simulating Lightcurve')

    lightcurve = hstack(lightcurve)

    return lightcurve

def loading_bar(decimal_percentage, text = ''):
    bar = '#'*int(decimal_percentage*20)
    print('{2} Loading:[{0:<20}] {1:.1f}%'.format(bar,decimal_percentage*100, text), end = '\r')
    if decimal_percentage == 1:
        print('')




if __name__ == '__main__':
    main()


