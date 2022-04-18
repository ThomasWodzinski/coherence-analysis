# -*- coding: utf-8 -*-
"""dph_deconvolution_v14.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Wc3gI82USZemfqb1lb8FIIQS1V7lvcPw

# imports
"""
# %% Imports

import time
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches

from csv import writer

from pathlib import Path  # see https://docs.python.org/3/library/pathlib.html#basic-use

import collections

from ipywidgets import (
    interact,
    interactive,
    fixed,
    interact_manual,
    Button,
    VBox,
    HBox,
    interactive,
    interactive_output,
)
import ipywidgets as widgets


import h5py

import math
import scipy

import pandas as pd

# pip install lmfit

from lmfit import Model

# everything for deconvolution method

# Garbage Collector - use it like gc.collect() from https://stackoverflow.com/a/61193594
import gc

from scipy.signal import convolve2d as conv2

from skimage import color, data, restoration

from scipy import fftpack

from scipy.optimize import curve_fit
from scipy.optimize import brenth
from scipy.optimize import minimize_scalar
import scipy.optimize as optimize

from IPython.display import display, clear_output

import os.path

# import pickle as pl

# Commented out IPython magic to ensure Python compatibility.
# %matplotlib inline


# %% deconvolution

# function definitions

def normalize(inputarray):
    normalized_array = inputarray / np.max(inputarray)
    return(normalized_array)

def gaussianbeam(x, a, m, w, offs):
    return a * np.exp(-2 * (x - m) ** 2 / w ** 2) + offs


def gauss2d(x, y, sigma_x, sigma_y):
    # Gprofile = (1/(2*np.pi*sigma)) * np.exp(-(x**2+y**2)/(2*sigma**2))
    Gprofile = np.exp(-(x ** 2 / (2 * sigma_x ** 2) + y ** 2 / (2 * sigma_y ** 2)))
    return Gprofile


def convolve(star, psf):
    star_fft = fftpack.fftshift(fftpack.fftn(star))
    psf_fft = fftpack.fftshift(fftpack.fftn(psf))
    return fftpack.fftshift(fftpack.ifftn(fftpack.ifftshift(star_fft * psf_fft)))


def deconvolve(star, psf):
    star_fft = fftpack.fftshift(fftpack.fftn(star))
    psf_fft = fftpack.fftshift(fftpack.fftn(psf))
    return fftpack.fftshift(fftpack.ifftn(fftpack.ifftshift(star_fft / psf_fft)))


def mean2(x):
    y = np.sum(x) / np.size(x)
    return y


def corr2(a, b):
    a = a - mean2(a)
    b = b - mean2(b)

    r = (a * b).sum() / math.sqrt((a * a).sum() * (b * b).sum())
    return r


def chi2_distance(histA, histB, eps=1e-10):
    # compute the chi-squared distance
    d = 0.5 * np.sum([((a - b) ** 2) / (a + b + eps) for (a, b) in zip(histA, histB)])

    # return the chi-squared distance
    return d


def calc_sigma_F_gamma_um(sigma_gamma_um, n, dX_1, wavelength_nm, create_figure):

    z = 5781 * 1e-3
    z_0 = 1067 * 1e-3
    z_T = z + z_0
    z_eff = z * z_0 / (z_T)
    # dX_1 = 13 * 1e-6

    wavelength = wavelength_nm * 1e-9

    # number of pixels
    # n = partiallycoherent.shape[0]
    # n = 1024
    nx = n
    ny = nx

    # pixel size of the detector dX_1

    dY_1 = dX_1

    # 2D grid and axes at the CCD:
    x = np.arange(-n / 2, n / 2, 1)
    y = np.arange(-n / 2, n / 2, 1)
    X1_axis, Y1_axis = np.meshgrid(x * dX_1, y * dX_1, sparse=False)

    # "pixelsize" at the pinholes:
    dX_2 = wavelength * z / (n * dX_1)
    dY_2 = wavelength * z / (n * dY_1)

    # 2D grid and axes at the double pinholes:
    X2_axis, Y2_axis = np.meshgrid(x * dX_2, y * dY_2, sparse=False)

    # assuming coherence length xi = sigma_gamma at the pinholes
    sigma_x_gamma_um = sigma_gamma_um
    sigma_y_gamma_um = sigma_x_gamma_um

    # gamma at the pinholes
    gamma = gauss2d(X2_axis / dX_2, Y2_axis / dX_2, sigma_x_gamma_um * 1e-6 / dX_2, sigma_y_gamma_um * 1e-6 / dX_2)

    xdata = list(range(n))
    ydata = abs(gamma)[int(n / 2), :]
    p0 = (int(n / 2), 1)
    popt_gauss, pcov_gaussian = curve_fit(lambda x, m, w: gaussianbeam(x, 1, m, w, 0), xdata, ydata, p0)
    sigma_x_gamma_px = popt_gauss[1] / 2
    sigma_x_gamma_um = sigma_x_gamma_px * dX_2 * 1e6

    if create_figure == True:
        fig, (ax1, ax2) = plt.subplots(1, 2, dpi=300)
        ax1.imshow(
            abs(gamma), cmap="jet", extent=((-n / 2) * dX_2, (+n / 2 - 1) * dX_2, -n / 2 * dX_2, (+n / 2 - 1) * dX_2)
        )
        ax1.set_title("gamma at pinholes $\sigma = $" + str(round(sigma_x_gamma_um, 1)) + "um", fontsize=8)

    # propagate to the detector
    F_gamma = fftpack.fftshift(fftpack.fftn(fftpack.ifftshift(gamma)))
    F_gamma = abs(F_gamma)
    F_gamma = F_gamma / np.max(F_gamma)
    if create_figure == True:
        ax2.imshow(
            abs(F_gamma), cmap="jet", extent=((-n / 2) * dX_1, (+n / 2 - 1) * dX_1, -n / 2 * dX_1, (+n / 2 - 1) * dX_1)
        )

    # determine sigma_F_gamma at the detector
    xdata = list(range(n))
    ydata = F_gamma[int(n / 2), :]
    p0 = (int(n / 2), 1)
    popt_gauss, pcov_gaussian = curve_fit(lambda x, m, w: gaussianbeam(x, 1, m, w, 0), xdata, ydata, p0)
    sigma_x_F_gamma_px = popt_gauss[1] / 2
    sigma_x_F_gamma_um = sigma_x_F_gamma_px * dX_1 * 1e6
    if create_figure == True:
        ax2.set_title("F_gamma at detector $\sigma = $" + str(round(sigma_x_F_gamma_um, 1)) + "um", fontsize=8)
        fig.clf()
        gc.collect()

    return sigma_x_F_gamma_um


"""### scan only in x for a given y"""


def deconvmethod_2d_x(
    partiallycoherent,
    z,
    dX_1,
    profilewidth,
    pixis_centery_px,
    wavelength,
    xi_um_guess,
    sigma_y_F_gamma_um_guess,
    crop_px,
    sigma_x_F_gamma_um_multiplier,
    scan_x,
    create_figure,
):

    # number of pixels
    n = partiallycoherent.shape[0]
    nx = n
    ny = nx

    # pixel size of the detector dX_1
    dY_1 = dX_1

    # 2D grid and axes at the CCD:
    # x = np.arange(-n/2, n/2, 1) * dX_1
    # y = np.arange(-n/2, n/2, 1) * dX_1
    x = np.arange(-n / 2, n / 2, 1)
    y = np.arange(-n / 2, n / 2, 1)
    X1_axis, Y1_axis = np.meshgrid(x * dX_1, y * dX_1, sparse=False)
    # X1_axis, Y1_axis = np.meshgrid(x, y, sparse=False)

    # "pixelsize" at the pinholes:
    dX_2 = wavelength * z / (n * dX_1)
    dY_2 = wavelength * z / (n * dY_1)

    # 2D grid and axes at the double pinholes:
    X2_axis, Y2_axis = np.meshgrid(x * dX_2, y * dY_2, sparse=False)

    if create_figure == True:
        fig = plt.figure(constrained_layout=False, figsize=(10, 6), dpi=300)
        gs = gridspec.GridSpec(8, 3, figure=fig)
        ax00 = fig.add_subplot(gs[0, 0])
        ax10 = fig.add_subplot(gs[1, 0])
        ax20 = fig.add_subplot(gs[2, 0])
        ax30 = fig.add_subplot(gs[3, 0])
        ax40 = fig.add_subplot(gs[4, 0])
        ax50 = fig.add_subplot(gs[5, 0])
        ax60 = fig.add_subplot(gs[6, 0])
        ax70 = fig.add_subplot(gs[7, 0])

        ax = fig.add_subplot(gs[:, 1:])

    z = 5781 * 1e-3
    z_0 = 1067 * 1e-3
    z_T = z + z_0
    z_eff = z * z_0 / (z_T)
    dX_1 = 13 * 1e-6

    # guess sigma_y_F_gamma_um to be the same as the beams rms width
    # sigma_y_F_gamma_um_guess = calc_sigma_F_gamma_um(xi_um_guess, n, dX_1, wavelength*1e9, False)
    sigma_y_F_gamma_um = sigma_y_F_gamma_um_guess

    sigma_x_F_gamma_um_list = []
    # fullycoherent_profile_min_list = np.array(sigma_x_F_gamma_um_list_length * [np.nan])
    fullycoherent_profile_min_list = []

    partiallycoherent_profile = np.mean(
        partiallycoherent[pixis_centery_px - int(profilewidth / 2) : pixis_centery_px + int(profilewidth / 2), :],
        axis=0,
    )
    partiallycoherent_profile = normalize(partiallycoherent_profile)

    if create_figure == True:
        ax70.cla()

    # to do: guess sigma_x_F_gamma_um to be the same as the beams rms width
    
    if scan_x == True:
        sigma_x_F_gamma_um_guess = calc_sigma_F_gamma_um(xi_um_guess, n, dX_1, wavelength * 1e9, False)
        sigma_x_F_gamma_um = sigma_x_F_gamma_um_guess
    else:
        sigma_x_F_gamma_um = sigma_y_F_gamma_um


    scratch_dir = Path("g:/My Drive/PhD/coherence/data/scratch_cc/")
    savefigure = True
    if savefigure == True:
        savefigure_dir = Path(str(scratch_dir) + "/" + 'deconvmethod_steps')
        if os.path.isdir(savefigure_dir) == False:
            os.mkdir(savefigure_dir)

        files = []
        files.extend(savefigure_dir.glob('*'+ 'ystep' + '*'))
        ystep_index_list = []
        if len(files) > 0:
            for f in files:
                filename = os.path.basename(f)
                ystep_index_list.append(int(filename.split('_')[1]))
            ystep_index_max = max(ystep_index_list)
            ystep = ystep_index_max + 1
        else:
            ystep = 0


    # for sigma_x_F_gamma_um in sigma_x_F_gamma_um_list:

    step_max = 5
    for i in np.arange(step_max): # [0,1,2]

        if scan_x == False:
            sigma_y_F_gamma_um = sigma_x_F_gamma_um

        sigma_x_F_gamma = sigma_x_F_gamma_um * 1e-6
        sigma_y_F_gamma = sigma_y_F_gamma_um * 1e-6
        
        sigma_x_F_gamma_um_list.append(sigma_x_F_gamma_um)

        F_gamma = gauss2d(X1_axis / dX_1, Y1_axis / dY_1, sigma_x_F_gamma / dX_1, sigma_y_F_gamma / dX_1)

        fullycoherent = restoration.wiener(partiallycoherent, F_gamma, 1)
        fullycoherent = fullycoherent / np.max(fullycoherent[crop_px:-crop_px, crop_px:-crop_px])

        fullycoherent_profile = np.mean(
            fullycoherent[pixis_centery_px - int(profilewidth / 2) : pixis_centery_px + int(profilewidth / 2), :],
            axis=0,
        )

        fullycoherent_profile = fullycoherent_profile / np.max(
            fullycoherent_profile[crop_px:-crop_px]
        )  # ignore what happens on the edges

        fullycoherent_profile_min = np.min(fullycoherent_profile[crop_px:-crop_px])  # ignore what happens on the edges
        fullycoherent_profile_min_list.append(fullycoherent_profile_min)

        if create_figure == True:

            csvfile = os.path.join(
                    savefigure_dir,
                    'sigma_y_F_gamma_um_guess_scan.csv')
            if os.path.exists(csvfile):
                df_deconv_scany = pd.read_csv(Path.joinpath(scratch_dir, 'deconvmethod_steps', "sigma_y_F_gamma_um_guess_scan.csv"),
                                header=None, names=['ystep', 'sigma_y_F_gamma_um_guess', 'chi2distance'])
                ax60.cla()
                ax60.scatter(df_deconv_scany['ystep'], df_deconv_scany['chi2distance'])


            # ax70.cla()
            # print(sigma_x_F_gamma_um_list)
            # print(fullycoherent_profile_min_list)
            ax70.scatter(sigma_x_F_gamma_um, fullycoherent_profile_min)
            # ax70.set_xlim([sigma_x_F_gamma_um_min, sigma_x_F_gamma_um_max])
            # ax70.set_ylim(
            #     [
            #         -np.min(partiallycoherent_profile[crop_px:-crop_px]),
            #         np.min(partiallycoherent_profile[crop_px:-crop_px]),
            #     ]
            # )
            ax70.axhline(0, color="k")
            # plt.title('sigma_x_F_gamma=' + str(sigma_x_F_gamma_um) + ' sigma_y_F_gamma=' + str(sigma_y_F_gamma_um) + ' fullycoherent_profile_min=' + str(fullycoherent_profile_min))

            n = partiallycoherent_profile.shape[0]
            xdata = np.linspace((-n / 2) * dX_1 * 1e3, (+n / 2 - 1) * dX_1 * 1e3, n)

            ax.cla()
            ax.plot(xdata, partiallycoherent_profile, "b-", label="measured partially coherent", linewidth=1)
            ax.plot(xdata, fullycoherent_profile, "r-", label="recovered fully coherent", linewidth=1)
            ax.axhline(0, color="k")
            ax.axvline(-(n/2-crop_px) * dX_1 * 1e3, color="k")
            ax.axvline((n/2-crop_px) * dX_1 * 1e3, color="k")
            ax.set_xlabel("x / mm", fontsize=8)
            ax.set_ylabel("Intensity / a.u.", fontsize=8)
            ax.set_ylim(-0.2,1.2)

            plt.title('i='+str(i))

            # plt.title('d / $\mu$m = '+str(int(separation_um)) + ' coherence length $\\xi_x$ / $\mu$m = ' + str(round(xi_x_um_list[index_opt],2)) + ' $\\xi_y$ / $\mu$m = ' + str(round(xi_y_um_list[index_opt],2)), fontsize=16)

            # see https://stackoverflow.com/a/29675706
            display(plt.gcf())
          
            if savefigure == True:
                plt.savefig(
                    os.path.join(
                    savefigure_dir,
                    'ystep_'
                    + str(ystep)
                    + '_step_'
                    + str(i)
                    + ".png"),
                    dpi=300,
                    facecolor="w",
                    edgecolor="w",
                    orientation="portrait",
                    papertype=None,
                    format=None,
                    transparent=False,
                    bbox_inches=0,
                    pad_inches=0.1,
                    frameon=None,
                )

            clear_output(wait=True)

        if fullycoherent_profile_min < 0 and i==0:
            sigma_x_F_gamma_um = sigma_x_F_gamma_um / sigma_x_F_gamma_um_multiplier
        else:
            if i==0:
                sigma_x_F_gamma_um = sigma_x_F_gamma_um * sigma_x_F_gamma_um_multiplier
            else:
                if i > 1 and (fullycoherent_profile_min * fullycoherent_profile_min_list[i-1] < 0) or (fullycoherent_profile_min * fullycoherent_profile_min_list[i-2] < 0):
                    break
                else:
                    sigma_x_F_gamma_um = sigma_x_F_gamma_um_list[i-1] - 1.05 * fullycoherent_profile_min_list[i-1] * (
                        (sigma_x_F_gamma_um_list[i] - sigma_x_F_gamma_um_list[i-1])/(fullycoherent_profile_min_list[i]-fullycoherent_profile_min_list[i-1]))


    xdata = np.array(sigma_x_F_gamma_um_list)
    ydata = np.array(fullycoherent_profile_min_list)

    def func(x, a, b, c):
        return a * x ** 2 + b * x + c

    popt_func, pcov_func = curve_fit(func, xdata, ydata)
    a = popt_func[0]
    b = popt_func[1]
    c = popt_func[2]

    try:
        sigma_x_F_gamma_um_opt = brenth(func, np.min(xdata), np.max(xdata), args=(a, b, c))
    except:
        sigma_x_F_gamma_um_opt = np.nan
              
    
    if create_figure == True:
        ax70.plot(np.array(sigma_x_F_gamma_um_list), func(np.array(sigma_x_F_gamma_um_list), a, b, c))
        ax70.axvline(sigma_x_F_gamma_um_opt)

    if sigma_x_F_gamma_um_opt > 0:

        sigma_x_F_gamma = sigma_x_F_gamma_um_opt * 1e-6
        if scan_x == False:
            sigma_y_F_gamma = sigma_x_F_gamma
        else:
            sigma_y_F_gamma = sigma_y_F_gamma_um * 1e-6
        F_gamma = gauss2d(X1_axis / dX_1, Y1_axis / dY_1, sigma_x_F_gamma / dX_1, sigma_y_F_gamma / dX_1)

        fullycoherent_opt = restoration.wiener(partiallycoherent, F_gamma, 1)
        fullycoherent_opt = fullycoherent_opt / np.max(fullycoherent_opt[crop_px:-crop_px, crop_px:-crop_px])

        fullycoherent_profile_opt = np.mean(
            fullycoherent_opt[pixis_centery_px - int(profilewidth / 2) : pixis_centery_px + int(profilewidth / 2), :],
            axis=0,
        )
        fullycoherent_profile_opt = fullycoherent_profile_opt / np.max(
            fullycoherent_profile_opt[crop_px:-crop_px]
        )  # ignore what happens on the edges

        # F_gamma = gauss2d(
        #     X1_axis / dX_1, Y1_axis / dY_1, sigma_x_F_gamma_um_opt * 1e-6 / dX_1, sigma_y_F_gamma_um * 1e-6 / dX_1
        # )
        gamma = fftpack.fftshift(fftpack.ifftn(fftpack.ifftshift(F_gamma)))

        partiallycoherent_rec = np.abs(convolve(fullycoherent_opt, F_gamma))
        partiallycoherent_rec = normalize(partiallycoherent_rec)
        partiallycoherent_rec_profile = np.mean(
            partiallycoherent_rec[pixis_centery_px - int(profilewidth / 2) : pixis_centery_px + int(profilewidth / 2), :],
            axis=0,
        )
        partiallycoherent_rec_profile = partiallycoherent_rec_profile / np.max(partiallycoherent_rec_profile[crop_px:-crop_px])
        

        

        # determine chi2 distance
        number_of_bins = 100
        hist1, bin_edges1 = np.histogram(partiallycoherent.ravel(), bins=np.linspace(0, 1, number_of_bins))
        hist2, bin_edges2 = np.histogram(partiallycoherent_rec.ravel(), bins=np.linspace(0, 1, number_of_bins))
        chi2distance = chi2_distance(hist1, hist2)

        xdata = list(range(n))
        ydata = fullycoherent[pixis_centery_px, :]
        ydata = ydata / np.max(ydata)

        abs_gamma = np.abs(gamma)
        abs_gamma = abs_gamma / np.max(abs_gamma)

        xdata = list(range(n))
        ydata = abs_gamma[int(n / 2), :]
        p0 = (int(n / 2), 1)
        try:
            popt_gauss, pcov_gaussian = curve_fit(lambda x, m, w: gaussianbeam(x, 1, m, w, 0), xdata, ydata, p0)
        except:
            1
        xi_x_px = popt_gauss[1] / 2
        xi_x_um = xi_x_px * dX_2 * 1e6

        xdata = list(range(n))
        ydata = abs_gamma[:, int(n / 2)]
        p0 = (int(n / 2), 1)
        try:
            popt_gauss, pcov_gaussian = curve_fit(lambda x, m, w: gaussianbeam(x, 1, m, w, 0), xdata, ydata, p0)
        except:
            1
        xi_y_px = popt_gauss[1] / 2
        xi_y_um = xi_y_px * dX_2 * 1e6

        # print(str(round(xi_x_um, 2)) + "," + str(round(xi_y_um, 2)))

        # print('coherence length xi/um = ' + str(xi_um))

        A_bp = fftpack.fftshift(fftpack.ifftn(fftpack.ifftshift(np.sqrt(partiallycoherent))))  # amplitude
        I_bp = np.abs(A_bp) ** 2  # intensity

        list_data = [ystep, sigma_y_F_gamma_um_guess, chi2distance]
        csvfile = os.path.join(
                    savefigure_dir,
                    'sigma_y_F_gamma_um_guess_scan.csv')
        with open(csvfile, 'a', newline='') as f_object:  
            writer_object = writer(f_object)
            writer_object.writerow(list_data)  
            f_object.close()

        if os.path.exists(csvfile):
                df_deconv_scany = pd.read_csv(Path.joinpath(scratch_dir, 'deconvmethod_steps', "sigma_y_F_gamma_um_guess_scan.csv"),
                                header=None, names=['ystep', 'sigma_y_F_gamma_um_guess', 'chi2distance'])
                ax60.cla()
                ax60.scatter(df_deconv_scany['ystep'], df_deconv_scany['chi2distance'])


        if create_figure == True:
            xdata = np.linspace((-n / 2) * dX_1 * 1e3, (+n / 2 - 1) * dX_1 * 1e3, n)
            ax.cla()
            ax.plot(xdata, partiallycoherent_profile, "b-", label="measured partially coherent", linewidth=1)
            ax.plot(xdata, fullycoherent_profile_opt, "r-", label="recovered fully coherent", linewidth=1)
            ax.plot(
                xdata, partiallycoherent_rec_profile, "g-", label="recovered partially coherent", linewidth=1,
            )
            # plt.plot(xdata, gaussianbeam(xdata, 1, popt_gauss[0] ,popt_gauss[1], 0), 'r-', label='fit: m=%5.1f px, w=%5.1f px' % tuple([popt_gauss[0] ,popt_gauss[1]]))
            ax.axhline(0, color="k")
            ax.axvline(-(n/2-crop_px) * dX_1 * 1e3, color="k")
            ax.axvline((n/2-crop_px) * dX_1 * 1e3, color="k")
            ax.set_xlabel("x / mm", fontsize=8)
            ax.set_ylabel("Intensity / a.u.", fontsize=8)
            ax.set_ylim(-0.2,1.2)
            # ax.set_xlim([xdata[0], xdata[-1]])
            plt.title('chi2distance='+str(chi2distance))

            display(plt.gcf())
           
            savefigure = True
            if savefigure == True:
                
                plt.savefig(
                    os.path.join(
                    savefigure_dir,
                    'ystep_'
                    + str(ystep)
                    + '_step_'
                    + str(i)
                    + ".png"),
                    dpi=300,
                    facecolor="w",
                    edgecolor="w",
                    orientation="portrait",
                    papertype=None,
                    format=None,
                    transparent=False,
                    bbox_inches=0,
                    pad_inches=0.1,
                    frameon=None,
                )

            plt.close(fig)
            clear_output(wait=True)

    else:
        fullycoherent_opt = np.nan
        fullycoherent_profile_opt = np.nan
        partiallycoherent_rec = np.nan
        partiallycoherent_rec_profile = np.nan
        sigma_x_F_gamma_um_opt = np.nan
        sigma_y_F_gamma_um = np.nan
        F_gamma = np.nan
        abs_gamma = np.nan
        xi_x_um = np.nan
        xi_y_um = np.nan
        I_bp = np.nan
        dX_2 = np.nan
        chi2distance = np.nan

    # decide what to return if it fails ...
    return (
        partiallycoherent_profile,
        fullycoherent_opt,
        fullycoherent_profile_opt,
        partiallycoherent_rec,
        partiallycoherent_rec_profile,
        sigma_x_F_gamma_um_opt,
        sigma_y_F_gamma_um,
        F_gamma,
        abs_gamma,
        xi_x_um,
        xi_y_um,
        I_bp,
        dX_2,
        chi2distance,
    )





# adapted from https://stackoverflow.com/a/54791154
def minimize_and_store(x0, f):
    all_x_i = [x0]
    all_f_i = [f(x0)]

    def store_to_array(X):
        print(X)
        all_x_i.append(X)
        all_f_i.append(f(X))

    optimize.minimize(calc_chi2distance, x0, callback=store_to_array, options={"disp": True, "maxiter": 5})
    return all_x_i, all_f_i


def deconvmethod(
    partiallycoherent,
    z,
    dX_1,
    profilewidth,
    pixis_centery_px,
    wavelength,
    xi_um_guess,
    sigma_y_F_gamma_um_guess,
    crop_px,
    sigma_x_F_gamma_um_multiplier,
    scan_x,
    xatol,
    create_figure,
):

    # chi2distance_minimize_result = minimize_and_store(sigma_y_F_gamma_um_guess, calc_chi2distance)
    
    scratch_dir = Path("g:/My Drive/PhD/coherence/data/scratch_cc/")
    savefigure = True
    if savefigure == True:
        savefigure_dir = Path(str(scratch_dir) + "/" + 'deconvmethod_steps')
        if os.path.isdir(savefigure_dir) == False:
            os.mkdir(savefigure_dir)

        files = []
        files.extend(savefigure_dir.glob('*'))
        for f in files:
            try:
                f.unlink()
            except OSError as e:
                print("Error: %s : %s" % (f, e.strerror))



    if scan_x == True:
        # find the minimal chi2 distance depending on sigma_y_F_gamma_um_guess
        chi2distance_minimize_result_bounded = optimize.minimize_scalar(
            lambda sigma_y_F_gamma_um_guess: deconvmethod_2d_x(
                partiallycoherent,
                z,
                dX_1,
                profilewidth,
                pixis_centery_px,
                wavelength,
                xi_um_guess,
                sigma_y_F_gamma_um_guess,
                crop_px,
                sigma_x_F_gamma_um_multiplier,
                scan_x,
                create_figure,
            )[-1],
            bounds=[sigma_y_F_gamma_um_guess / 4, sigma_y_F_gamma_um_guess * 2],
            method="bounded",
            options={"disp": 0, "maxiter": 50, "xatol": xatol},  # "disp": 3 to show info for all iterations
        )
        
        # start = datetime.now()
        # chi2distance_minimize_result_brent = optimize.minimize_scalar(
        #     calc_chi2distance,
        #     bracket=[sigma_y_F_gamma_um_guess / 4, sigma_y_F_gamma_um_guess * 2],
        #     method="brent",
        #     options={"maxiter": 50, "xtol": 1e-1},
        # )
        
        # see https://stackoverflow.com/questions/16739065/how-to-display-progress-of-scipy-optimize-function
        # print(chi2distance_minimize_result_brent)

        # use the optimal sigma_y_F_gamma_um_guess to determine the corresponding sigma_x_F_gamma_um and with it the coherence lengths xi_x and xi_y
        sigma_y_F_gamma_um_guess = chi2distance_minimize_result_bounded.x
    
    (
        partiallycoherent_profile,
        fullycoherent_opt,
        fullycoherent_profile_opt,
        partiallycoherent_rec,
        partiallycoherent_rec_profile,
        sigma_x_F_gamma_um_opt,
        sigma_y_F_gamma_um,
        F_gamma,
        abs_gamma,
        xi_x_um,
        xi_y_um,
        I_bp,
        dX_2,
        chi2distance,
    ) = deconvmethod_2d_x(
        partiallycoherent,
        z,
        dX_1,
        profilewidth,
        pixis_centery_px,
        wavelength,
        xi_um_guess,
        sigma_y_F_gamma_um_guess,
        crop_px,
        sigma_x_F_gamma_um_multiplier,
        scan_x,
        create_figure,
    )

    return (
        partiallycoherent_profile,
        fullycoherent_opt,
        fullycoherent_profile_opt,
        partiallycoherent_rec,
        partiallycoherent_rec_profile,
        sigma_x_F_gamma_um_opt,
        sigma_y_F_gamma_um,
        F_gamma,
        abs_gamma,
        xi_x_um,
        xi_y_um,
        I_bp,
        dX_2,
        chi2distance,
    )




# %%
