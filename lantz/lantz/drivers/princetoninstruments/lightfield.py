import numpy as np
from time import sleep

import clr
import sys
import os

# Import DLLs for running spectrometer via LightField
lf_root = os.environ['LIGHTFIELD_ROOT']
automation_path = lf_root + '\PrincetonInstruments.LightField.AutomationV4.dll'
addin_path = lf_root + '\AddInViews\PrincetonInstruments.LightFieldViewV4.dll'
support_path = lf_root + '\PrincetonInstruments.LightFieldAddInSupportServices.dll'

addin_class = clr.AddReference(addin_path);
automation_class = clr.AddReference(automation_path);
support_class = clr.AddReference(support_path);

import PrincetonInstruments.LightField as lf

# Import some system functions for interfacing with LightField code
clr.AddReference("System.Collections")
clr.AddReference("System.IO")
from System.Collections.Generic import List
from System import String
from System.IO import FileAccess

# Lantz imports
from lantz import Driver, Feat, DictFeat, Action



class LightFieldM:
    """
    Helper class for interfacing between the lantz driver and LightField
    software.
    """

    def __init__(self, visible):

        self._addinbase = lf.AddIns.AddInBase()
        self._automation = lf.Automation.Automation(visible, List[String](""))
        self._application = self._automation.LightFieldApplication
        self._experiment = self._application.Experiment

    @property
    def automation(self):
        return self._automation

    @property
    def addinbase(self):
        return self._addinbase

    @property
    def application(self):
        return self._application

    @property
    def experiment(self):
        return self._experiment

    def __del__(self):
        """
        Uses Python garbage collection method used to terminate
        AddInProcess.exe, if this is not done, LightField will not reopen
        properly.
        """
        self.automation.Dispose()
        print('Closed AddInProcess.exe')

    def set(self, setting, value):
        """
        Helper function for setting experiment parameters with basic value
        checking.
        """

        if self.experiment.Exists(setting):
            if self.experiment.IsValid(setting, value):

                self.experiment.SetValue(setting, value)

            else:

                # TODO: add proper exception?
                print('Invalid value: {} for setting: {}.'.format(value, setting))

        else:

            # TODO: add proper exceptions?
            print('Invalid setting:{}'.format(setting))

        return

    def get(self, setting):
        """
        Helper function for getting experiment parameters with a basic check
        to see if a specific setting is valid.
        """

        if self.experiment.Exists(setting):

            value = self.experiment.GetValue(setting)

        else:

            value = []
            print('Invalid setting: {}'.format(setting))

        return value

    def load_experiment(self, value):
        self.experiment.Load(value)

    def acquire(self):
        """
        Helper function to acquire the data from the PIXIS-style cameras.
        Your mileage may vary for the Pylon - need to check array reorganization
        since there is only a single vertical pixel.

        For a single frame, the data is returned as a 2D array (just raw counts
        from each pixel). Taking a section in the vertical (400-pixel) direction
        corresponds to wavelength averaging.

        For multiple frames, each exposure is stacked in a third dimension, so
        averaging can be performed simply by summing over the different planes.
        """

        acquisition_time = self.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime)
        num_frames =  self.get(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore)

        self.experiment.Acquire()

        sleep(0.001 * acquisition_time * num_frames) # waits exposure duration

        while self.experiment.IsRunning:
            sleep(0.1) # waits for experiment to finish

        last_file = self.application.FileManager.GetRecentlyAcquiredFileNames().GetItem(0)

        image_set = self.application.FileManager.OpenFile(last_file, FileAccess.Read)

        if image_set.Regions.Length == 1:

            if image_set.Frames == 1:

                frame = image_set.GetFrame(0, 0)
                data = np.reshape(np.fromiter(frame.GetData(),'uint16'), [frame.Width, frame.Height], order='F')

            else:
                data = np.array([])
                for i in range(0, image_set.Frames):

                    frame = image_set.GetFrame(0, i)
                    new_frame = np.fromiter(frame.GetData(), 'uint16')

                    new_frame = np.reshape(np.fromiter(frame.GetData(), 'uint16'), [frame.Width, frame.Height], order='F')
                    data = np.dstack((data, new_frame)) if data.size else new_frame


            return data


        else:
        # not sure when this situation actually arises, but I think multiple
        # regions of interest have to be set.
        #     data = cell(imageset.Regions.Length, 1)
            print('image_set.Regions not 1! this needs to be figured out!')
            print(image_set.Frames)
        #     for j in range(0, image_set.Regions.Length - 1):
        #
        #         if image_set.Frames == 1:
        #
        #             frame = image_set.GetFrame(j, 0)
        #             buf = np.reshape(np.fromiter(frame.GetData(), 'uint16'), frame.Width, frame.Height))
        #
        #         else:
        #
        #             buf = []
        #
        #             for i in range(0, image_set.Frames-1):
        #
        #                 frame = image_set.GetFrame(j, i)
        #                 buffer = np.dstack(buf, np.reshape(np.fromiter(frame.GetData(), 'uint16'), frame.Width, frame.Height, 1))
        #
        #         data[j+1] = buf

    def close(self):
        """
        """
        self.automation.Dispose()
        print('Closed AddInProcess.exe')


class Spectrometer(Driver):

    GRATINGS = ['[500nm,600][0][0]','[1.2um,300][1][0]','[500nm,150][2][0]']# TODO: make it pull gratings from SW directly

    def initialize(self):
        """
        Sets up LightField
        """
        self.lfm = LightFieldM(True)
        self.lfm.load_experiment('SpyreAutomation')

    def finalize(self):
        """
        Shuts the club downnnnn.
        """
        self.lfm.close()

    @Feat(units='nm')
    def center_wavelength(self):
        """
        Returns the center wavelength in nanometers.
        """
        return self.lfm.get(lf.AddIns.SpectrometerSettings.GratingCenterWavelength)

    def get_wavelengths(self):
        """
        Returns the wavelength calibration for a single frame.
        """
        size = self.lfm.experiment.SystemColumnCalibration.get_Length()

        result = np.empty(size)

        for _ in range(size):

            result[_] = self.lfm.experiment.SystemColumnCalibration[_]

        return result

    @center_wavelength.setter
    def center_wavelength(self, nanometers):
        """
        Sets the spectrometer center wavelength to nanometers.
        """
        # this avoids bug where if step and glue is selected, doesn't allow setting center wavelength
        self.lfm.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)

        return self.lfm.set(lf.AddIns.SpectrometerSettings.GratingCenterWavelength, nanometers)

    @Feat()
    def grating(self):
        """
        Returns the current grating.
        """
        return self.lfm.get(lf.AddIns.SpectrometerSettings.GratingSelected)

    @grating.setter
    def grating(self, grating):
        """
        Sets the current grating to be the one specified by parameter grating.
        """
        # TODO: figure out the format for setting this

        print('figure out the format for this')

    @Feat()
    def gratings(self):
        """
        Returns a list of all installed gratings.
        """
        break_down = False

        if break_down:

            import re

            for g in GRATINGS:

                match = re.search(r"\[(\d+\.?\d+[nu]m),(\d+)\]\[(\d+)\]\[(\d+)\])",g)
                blaze, g_per_mm, slot, turret = match.groups()

        return GRATINGS

    @Feat()
    def num_frames(self):
        """
        Returns the number of frames taken during the acquisition.
        """
        return self.lfm.get(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore)

    @num_frames.setter
    def num_frames(self, num_frames):
        """
        Sets the number of frames to be taken during acquisition to number.
        """
        return self.lfm.set(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore, num_frames)

    @Feat()
    def exposure_time(self):
        """
        Returns the single frame exposure time (in ms).
        """
        return self.lfm.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime)

    @exposure_time.setter
    def exposure_time(self, ms):
        """
        Sets the single frame exposure time to be ms (in milliseconds).
        """
        return self.lfm.set(lf.AddIns.CameraSettings.ShutterTimingExposureTime, ms)

    @Feat()
    def sensor_temperature(self):
        """
        Returns the current sensor temperature (in degrees Celsius).
        """
        return self.lfm.get(lf.AddIns.CameraSettings.SensorTemperatureReading)

    @Feat()
    def sensor_setpoint(self):
        """
        Returns the sensor setpoint temperature (in degrees Celsius).
        """
        return self.lfm.get(lf.AddIns.CameraSettings.SensorTemperatureSetPoint)

    @sensor_setpoint.setter
    def sensor_setpoint(self, deg_C):
        """
        Sets the sensor target temperature (in degrees Celsius) to deg_C.
        """
        return self.lfm.set(lf.AddIns.CameraSettings.SensorTemperatureSetPoint, deg_C)


    @Action()
    def acquire_frame(self):
        """
        Acquires a frame (or series of frames) from the spectrometer, and the
        corresponding wavelength data.
        """
        return self.lfm.acquire(), self.get_wavelengths()

    @Action()
    def acquire_step_and_glue(self, wavelength_range):
        """
        Acquires a step and glue (wavelength sweep) over the specified range.

        Wavelength range must have two elements (both in nm), corresponding
        to the starting and stopping wavelengths.

        Note that the wavelength must be calibrated for this to be meaningful!
        """

        lambda_min = wavelength_range[0]
        lambda_max = wavelength_range[1]

        try:

            self.lfm.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, True)



        except:

            self.lfm.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
            print('Unable to perform step and glue, check settings.')

            return

        self.lfm.set(lf.AddIns.ExperimentSettings.StepAndGlueStartingWavelength, lambda_min)
        self.lfm.set(lf.AddIns.ExperimentSettings.StepAndGlueEndingWavelength, lambda_max)

        data = self.lfm.acquire()

        wavelength = np.linspace(lambda_min, lambda_max, data.shape[0])

        print('Wavelength data is not strictly correct, this just interpolates.')
        print('TODO: figure out how step and glue determines which wavelengths are used. This might be done in post processing.')
        print('If you want the true values, use the actual .spe file that is generated.')

        self.lfm.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)

        return data, wavelength


    @Action()
    def acquire_background(self):
        """
        Acquires a background file and sets it to be used in the current scan.
        """
        # TODO: take background file, and save it in a location where it be accessed later

        print('not yet implemented')


def lantz_test():

    s = Spectrometer()
    s.initialize()

    print('Exposure time: {}ms'.format(s.exposure_time))
    s.exposure_time = 2.0
    print('Exposure time: {}ms'.format(s.exposure_time))
    s.exposure_time = 1.5
    print('Exposure time: {}ms'.format(s.exposure_time))

    print('Number of frames: {}'.format(s.num_frames))
    s.num_frames = 1
    print('Number of frames: {}'.format(s.num_frames))
    s.num_frames = 10
    print('Number of frames: {}'.format(s.num_frames))

    print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))
    s.sensor_setpoint = -60.0
    print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))
    s.sensor_setpoint = -70.0
    print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))


    print('Sensor temperature: {} C'.format(s.sensor_temperature))

    print('Grating: {}'.format(s.grating))

    print('Center wavelength:{}'.format(s.center_wavelength))
    s.center_wavelength = 700.0
    print('Center wavelength:{}'.format(s.center_wavelength))
    s.center_wavelength = 730.0
    print('Center wavelength:{}'.format(s.center_wavelength))


    print('Acquring single frame')
    s.num_frames = 1
    data, wavelength = s.acquire_frame()
    print(data.shape)

    s.num_frames = 10
    print('Acquring 10 frames')
    data, wavelength = s.acquire_frame()
    print(data.shape)


    data, wavelength = s.acquire_step_and_glue([500.0, 950.0])

    print(data.shape, wavelength.shape)

    s.finalize()


def test():

    #import matplotlib.pyplot as plt

    lfm = LightFieldM(True)
    lfm.load_experiment('SpyreAutomation')

    lfm.set_frames(5)
    print(lfm.get(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore))
    lfm.set_frames(10)
    print(lfm.get(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore))
    lfm.set_frames(1)

    print(lfm.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime))
    lfm.set_exposure(0.5)
    print(lfm.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime))
    lfm.set_exposure(1.5)
    print(lfm.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime))


    #data = lfm.acquire()
    #print(data)
    #plt.plot(data)
    #plt.show()

    lfm.set_frames(10)
    #data = lfm.acquire()
    #print(data)
    #plt.plot(data)
    #plt.show()

if __name__ == "__main__":
    #test()
    lantz_test()
