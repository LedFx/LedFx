from enum import Enum


class Mode(Enum):
    HOLD = 1
    BOUNCE = 2
    HARD_ZERO = 3
    DECELERATE = 4


class Scalar():
    def __init__(self, val, delta, target, target_2, mode):
        self.val = val
        self.delta = delta
        self.target = target
        self.target_2 = target_2
        self.mode = mode

    def update(self, passed_time):
        self.val += self.delta * passed_time
        if self.delta > 0:
            self.val = min(self.val, self.target)
        else:
            self.val = max(self.val, self.target)
        if self.val == self.target:
            if self.mode == Mode.HOLD:
                self.delta = 0
            elif self.mode == Mode.BOUNCE:
                self.delta = -self.delta
                self.target, self.target_2 = self.target_2, self.target
            elif self.mode == Mode.HARD_ZERO:
                self.delta = 0
                self.val = 0
            elif self.mode == Mode.DECELERATE:
                self.delta = self.delta * 0.5


class Pose():
    # we need a class to represent a 2d pose and all of its dynamics
    # this class will be used to represent
    #  life of the active render and manipulation of the pose in seconds
    # vector values all of the range -1 to 1
    #  pos (x,y), ang and size
    # vector values of the range of 0 to 1\
    #  alpha the blend alpha of the related object
    # delta values of increase in vector values over time on a second unit
    #  d_pos in a vector of direction and value per sec
    #  d_rotation as a value per sec
    #  d_size as a value per sec
    #  d_alpha as a value per sec
    # limit values of vector values and what happens when they ge there
    #  position, rotation and size, alpha
    # modifiers to the delta values over time
    #  m_pos accel dec linear and angular
    #  m_rotation rate of change of d_rotation
    #  m_size rate of change of d_size
    #  m_alpha rate of change of d_alpha

    # we will start with an init class that just create the vector values
    # all other deltas and modifiers will be added later, this will allow incremental implementation

    def __init__(self, x, y, ang, size, life, alpha = 1.0):
        self.x = x
        self.y = y
        self.ang = ang
        self.size = size
        self.life = life
        self.alpha = alpha

        self.d_pos = None
        self.d_rotation = 0
        self.d_size = None
        self.m_pos = None
        self.m_rotation = None
        self.m_size = None
        self.limit_pos = None
        self.limit_rotation = None
        self.limit_size = None

    def set_vectors(self, x, y, ang, size, life, alpha = 1.0):
        self.x = x
        self.y = y
        self.ang = ang
        self.size = size
        self.life = life
        self.alpha = alpha

    def set_deltas(self, d_pos, d_rotation, d_size):
        self.d_pos = d_pos
        self.d_rotation = d_rotation
        self.d_size = d_size

    def update(self, passed_time):
        self.life -= passed_time
        if self.life <= 0.0:
            return False

        self.ang = (((self.ang + 1 )+ self.d_rotation * passed_time ) % 2 ) - 1
        return True