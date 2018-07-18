# Copyright (c) 2018 Avanade
# Author: Thor Schueler
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# pylint: disable=C0103
"""Module allowing control of a meArm using the RPI"""
import time
import logging
import controller
import kinematics
import atexit

class me_arm(object):
    """Control meArm"""

    # servo defaults
    servo_frequency = 50            # default servo frequency
    servo_min_pulse = 0.6           # default servo min pulse (tuned for SG90S from Mizui)
    servo_max_pulse = 2.3           # default servo max pulse (tuned for SG90S from Mizui)
    servo_neutral_pulse = 1.4       # default servo neutral pulse (tuned for SG90S from Mizui)
    servo_min_angle = -85.0         # default servo min angle (tuned for SG90S from Mizui)
    servo_max_angle = 85.0          # default servo max angle (tuned for SG90S from Mizui)
    servo_neutral_angle = -0.0      # default servo neutral angle (tuned for SG90S from Mizui)
    pulse_resolution = 4096         # tuned to generate exact pulse width accounting for calculation rounding error
    board_frequency = 25000000      # PWM board frequency.

    # arm neutrals and boundaries
    elbow_neutral_angle = 0.0       # servo angle for elbow neutral position
    shoulder_neutral_angle = 40.0   # servo angle for shoulder neutral position
    hip_neutral_angle = 0.0         # servo angle for hip neutral position

    elbow_max_angle = 84.5          # servo angle for elbow max position
    shoulder_max_angle = 65.0       # servo angle for shoulder max position
    hip_max_angle = 84.5            # servo angle for hip max position

    elbow_min_angle = -25.0         # servo angle for elbow min position
    shoulder_min_angle = -15.0      # servo angle for shoulder min position
    hip_min_angle = -84.5           # servo angle for hip min position

    gripper_closed_angle = 27.5     # servo angle for closed gripper
    gripper_open_angle = -20.0      # servo angle for open gripper
    inc = 0.5                       # servo movement increment in degrees

    Instance = None

    def __init__(self, 
            hip_channel: int = 15,
            elbow_channel: int = 12,
            shoulder_channel: int = 13,
            gripper_channel: int = 14,
            servo_frequency: int = None,
            board_frequency: int = None,
            resolution: int = None,
            initialize: bool = True):
        """__init__
        Default initialization of arm
        
        :param hip_channel: The channel for the hip servo.
        :type hip_channel: int

        :param elbow_channel: The channel for the elbow servo.
        :type elbow_channel: int

        :param shoulder_channel: The channel for the shoulder servo.
        :type shoulder_channel: int

        :param gripper_channel: The channel for the gripper servo.
        :type gripper_channel: int

        :param servo_frequency: The servo frequency.
        :type servo_frequency: int

        :param board_frequency: The frequency on which the PWM board operates. This needs to be tuned.
        :type board_frequency: int

        :param resolution: The pulse resolution. This is generally 12bit (4096).
        :type resolution: int

        :param initialize: True to immidiately run the servo initialization, false to adjuist values after construction.
        :type initialize: bool      

        """
        if hip_channel < 0 or hip_channel > 15 or \
           elbow_channel < 0 or elbow_channel > 15 or \
           shoulder_channel < 0 or shoulder_channel > 15 or \
           gripper_channel < 0 or gripper_channel > 15:
            raise ValueError('Servo channel values must be between 0 and 15')

        if me_arm.Instance is not None:
            msg = "meArm Instance already exists. Cannot create a new instance. Release the existing \
                instance by calling me_arm.Instance.shutdown()"
            logger.error(msg)
            raise Exception(msg)

        if servo_frequency is None: servo_frequency = me_arm.servo_frequency
        if board_frequency is None: board_frequency = me_arm.board_frequency
        if resolution is None: resolution = me_arm.pulse_resolution
        self.kinematics = kinematics.Kinematics()
        self.logger = logging.getLogger(__name__)
        self.hip_channel = hip_channel
        self.elbow_channel = elbow_channel
        self.shoulder_channel = shoulder_channel
        self.gripper_channel = gripper_channel
        self.__setup_defaults()

        # Initialise the PCA9685 using the default address (0x40).
        self.pwm = controller.PCA9685(
            0x40, 
            None,
            board_frequency,
            resolution,
            servo_frequency)

        # Alternatively specify a different address and/or bus: controller.PCA9685(address=0x40, busnum=2)
        if initialize: self.initialize()
        me_arm.Instance = self
    
    def __setup_defaults(self):
        """__setup_defaults
        Setup defaults for the servos based on static defaults.
        """
        self.frequency = me_arm.servo_frequency

        # defaults for hip servo
        self.hip_min_pulse = me_arm.servo_min_pulse
        self.hip_max_pulse = me_arm.servo_max_pulse
        self.hip_neutral_pulse = me_arm.servo_neutral_pulse
        self.hip_min_angle = me_arm.servo_min_angle
        self.hip_max_angle = me_arm.servo_max_angle
        self.hip_neutral_angle = me_arm.servo_neutral_angle
        self.hip_resolution = me_arm.pulse_resolution

        # defaults for shoulder servo
        self.shoulder_min_pulse = me_arm.servo_min_pulse
        self.shoulder_max_pulse = me_arm.servo_max_pulse
        self.shoulder_neutral_pulse = me_arm.servo_neutral_pulse
        self.shoulder_min_angle = me_arm.servo_min_angle
        self.shoulder_max_angle = me_arm.servo_max_angle
        self.shoulder_neutral_angle = me_arm.servo_neutral_angle
        self.shoulder_resolution = me_arm.pulse_resolution

        # defaults for elbow servo
        self.elbow_min_pulse = me_arm.servo_min_pulse
        self.elbow_max_pulse = me_arm.servo_max_pulse
        self.elbow_neutral_pulse = me_arm.servo_neutral_pulse
        self.elbow_min_angle = me_arm.servo_min_angle
        self.elbow_max_angle = me_arm.servo_max_angle
        self.elbow_neutral_angle = me_arm.servo_neutral_angle
        self.elbow_resolution = me_arm.pulse_resolution

        # defaults for gripper servo
        self.gripper_min_pulse = me_arm.servo_min_pulse
        self.gripper_max_pulse = me_arm.servo_max_pulse
        self.gripper_neutral_pulse = me_arm.servo_neutral_pulse
        self.gripper_min_angle = me_arm.servo_min_angle
        self.gripper_max_angle = me_arm.servo_max_angle
        self.gripper_neutral_angle = me_arm.servo_neutral_angle
        self.gripper_resolution = me_arm.pulse_resolution

        #current angles
        self.elbow_angle = me_arm.elbow_neutral_angle
        self.shoulder_angle = me_arm.shoulder_neutral_angle
        self.hip_angle = me_arm.hip_neutral_angle
        x, y, z = self.kinematics.toCartesian(self.hip_angle, self.shoulder_angle, self.elbow_angle)
        self.position = kinematics.Point.fromCartesian(x, y, z)        

    @classmethod
    def createWithServoParameters(cls,
            hip_channel:int, elbow_channel:int, shoulder_channel:int, gripper_channel:int):
    
        if me_arm.Instance is not None: return me_arm.Instance

        obj = cls(hip_channel, elbow_channel, shoulder_channel, gripper_channel, False)

        #override defaults for servos
        obj.initialize()
        me_arm.Instance = obj
        return obj

    def close(self):
        """close
        Close the gripper, grabbing onto anything that might be there
        """
        self.pwm.set_servo_angle(self.gripper_channel, me_arm.gripper_closed_angle)
        time.sleep(0.3)

    def is_reachable(self, point:kinematics.Point) -> (bool, float, float, float):
        """is_reachable

        Returns True if the point is (theoretically) reachable by the gripper
        
        :param
        
        """
        hip, shoulder, elbow = self.kinematics.fromCartesian(point.x, point.y, point.z)
        isReachable = True
        if hip < me_arm.hip_min_angle or hip > me_arm.hip_max_angle: isReachable = False
        if shoulder < me_arm.shoulder_min_angle or shoulder > me_arm.shoulder_max_angle: isReachable = False
        if elbow < me_arm.elbow_min_angle or elbow > me_arm.elbow_max_angle: isReachable = False
        return isReachable, hip, shoulder, elbow
    
    def get_position(self) -> (kinematics.Point):
        """Returns the current position of the gripper"""
        return self.position

    def go_directly_to_point(self, target:kinematics.Point):
        """Set servo angles so as to place the gripper at a given Cartesian point as quickly as possible, without caring what path it takes to get there"""

        is_reachable, hip, shoulder, elbow = self.is_reachable(target)
        if not is_reachable:
            msg = "Point x: %f, y: %f, x: %f is not reachable" % (target.x, target.y, target.z)
            self.logger.error(msg)
            raise Exception(msg)       

        self.pwm.set_servo_angle(self.hip_channel, hip)
        self.pwm.set_servo_angle(self.shoulder_channel, shoulder)
        self.pwm.set_servo_angle(self.elbow_channel, elbow)
        self.position = target
        self.hip_angle = hip
        self.shoulder_angle = shoulder
        self.elbow_angle = elbow
        self.logger("Goto point x: %d, y: %d, z: %d", target.x, target.y, target.z)

    def go_to_point(self, target:kinematics.Point, resolution:int=10):
        """Travel in a straight line from current position to a requested position"""
        if not self.is_reachable(target)[0]:
            raise Exception("Point x: %f, y: %f, x: %f is not reachable" % (target.x, target.y, target.z))
        
        dist = self.position.distance(target)
        i = 0
        while i < dist:
            p = kinematics.Point.fromCartesian(
                self.position.x + (target.x - self.position.x) * i / dist, 
                self.position.y + (target.y - self.position.y) * i / dist, 
                self.position.z + (target.z - self.position.z) * i / dist)
            self.go_directly_to_point(p)
            time.sleep(0.05)
            i += resolution
        self.go_directly_to_point(target)
        time.sleep(0.05)

    def initialize(self):
        """Registers the servo."""
        self.pwm.add_servo(self.hip_channel, 
            self.hip_min_pulse, self.hip_max_pulse, self.hip_neutral_pulse,
            self.hip_min_angle, self.hip_max_angle, self.hip_neutral_angle)
        self.pwm.add_servo(self.shoulder_channel, 
            self.shoulder_min_pulse, self.shoulder_max_pulse, self.shoulder_neutral_pulse,
            self.shoulder_min_angle, self.shoulder_max_angle, self.shoulder_neutral_angle)
        self.pwm.add_servo(self.elbow_channel, 
            self.elbow_min_pulse, self.elbow_max_pulse, self.elbow_neutral_pulse,
            self.elbow_min_angle, self.elbow_max_angle, self.elbow_neutral_angle)
        self.pwm.add_servo(self.gripper_channel, 
            self.gripper_min_pulse, self.gripper_max_pulse, self.gripper_neutral_pulse,
            self.gripper_min_angle, self.gripper_max_angle, self.gripper_neutral_angle)

    def open(self):
        """Open the gripper, dropping whatever is being carried"""
        self.pwm.set_servo_angle(self.gripper_channel, me_arm.gripper_open_angle)
        time.sleep(0.3)

    def shutdown(self):
        """Resets the arm at neutral position and then resets the controller"""
        self.logger.info('Resetting arm and controller...')
        self.pwm.set_servo_angle(self.hip_channel, me_arm.hip_neutral_angle)
        self.pwm.set_servo_angle(self.shoulder_channel, me_arm.shoulder_neutral_angle)
        self.pwm.set_servo_angle(self.elbow_channel, me_arm.elbow_neutral_angle)
        self.pwm.set_servo_angle(self.gripper_channel, me_arm.gripper_open_angle)
        time.sleep(0.3)
        controller.software_reset()
        me_arm.Instance = None

    def test(self):
        """Simple loop to test the arm"""
        self.logger.info('Press Ctrl-C to quit...')
        self.pwm.set_servo_angle(self.hip_channel, self.hip_angle)
        self.pwm.set_servo_angle(self.shoulder_channel, self.shoulder_angle)
        self.pwm.set_servo_angle(self.elbow_channel, self.elbow_angle)
        self.close()
        while True:     
            while self.elbow_angle < me_arm.elbow_max_angle:
                self.pwm.set_servo_angle(self.elbow_channel, self.elbow_angle)
                self.elbow_angle += me_arm.inc

            while self.shoulder_angle > me_arm.shoulder_min_angle:
                self.pwm.set_servo_angle(self.shoulder_channel, self.shoulder_angle)
                self.shoulder_angle -= me_arm.inc

            self.close()

            while self.hip_angle > me_arm.hip_min_angle:
                self.pwm.set_servo_angle(self.hip_channel, self.hip_angle)
                self.hip_angle -= me_arm.inc

            while self.shoulder_angle < me_arm.shoulder_max_angle:
                self.pwm.set_servo_angle(self.shoulder_channel, self.shoulder_angle)
                self.shoulder_angle += me_arm.inc

            while self.elbow_angle > me_arm.elbow_min_angle:
                self.pwm.set_servo_angle(self.elbow_channel, self.elbow_angle)
                self.elbow_angle -= me_arm.inc

            while self.hip_angle < me_arm.hip_max_angle:
                self.pwm.set_servo_angle(self.hip_channel, self.hip_angle)
                self.hip_angle += me_arm.inc

            self.open()

            while self.hip_angle > me_arm.hip_neutral_angle:
                self.pwm.set_servo_angle(self.hip_channel, self.hip_angle)
                self.hip_angle -= me_arm.inc

def shutdown():
    if me_arm.Instance is not None:
        me_arm.Instance.shutdown()

atexit.register(shutdown)
