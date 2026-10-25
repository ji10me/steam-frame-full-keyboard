import ctypes as C
import json
import math
from pathlib import Path

PROFILE = Path.home() / '.local/state/frame-jis-keyboard/native-placement.json'


def rigid(matrix):
    """OpenVR coordinate transforms may contain inherited nonuniform scale."""
    if not all(math.isfinite(v) for row in matrix for v in row):
        raise ValueError('Nonfinite overlay transform')
    def unit(v):
        length = math.sqrt(sum(x*x for x in v))
        if length < .001:
            raise ValueError('Degenerate overlay transform')
        return [x/length for x in v]
    z = unit([matrix[r][2] for r in range(3)])
    x = [matrix[r][0] for r in range(3)]
    projection = sum(x[r]*z[r] for r in range(3))
    x = unit([x[r]-projection*z[r] for r in range(3)])
    y = [z[1]*x[2]-z[2]*x[1], z[2]*x[0]-z[0]*x[2], z[0]*x[1]-z[1]*x[0]]
    if sum(y[r]*matrix[r][1] for r in range(3)) <= 0:
        raise ValueError('Mirrored overlay transform')
    return [[x[r], y[r], z[r], matrix[r][3]] for r in range(3)]


def physical_width(geometry):
    return geometry['width'] * math.sqrt(sum(geometry['center'][r][0]**2 for r in range(3)))


def native_profile(parent, native):
    a, b = rigid(parent['center']), rigid(native['center'])
    width = physical_width(parent)
    if not .1 < width < 10:
        raise ValueError('Invalid parent size')
    offset = [sum(a[r][c]*(b[r][3]-a[r][3]) for r in range(3))/width for c in range(3)]
    # Measure relative to the bottom edge, so a taller window does not overlap.
    offset[1] += parent['scale'][1]/parent['scale'][0]/2
    return {'schema': 1, 'bottom_offset': offset,
            'width_ratio': physical_width(native)/width,
            'rotation': [[sum(a[k][r]*b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]}


def keyboard_pose(parent, profile=None, head=None):
    a = rigid(parent['center'])
    width = physical_width(parent)
    if not .1 < width < 10:
        raise ValueError('Invalid parent size')
    if profile is None:
        angle = math.radians(-50)
        profile = {'bottom_offset': [0, -.29, .337], 'width_ratio': .75,
                   'rotation': [[1, 0, 0], [0, math.cos(angle), -math.sin(angle)],
                                [0, math.sin(angle), math.cos(angle)]]}
    local = list(profile['bottom_offset'])
    local[1] -= parent['scale'][1]/parent['scale'][0]/2
    rotation = profile['rotation']
    result = [[sum(a[r][k]*rotation[k][c] for k in range(3)) for c in range(3)] +
              [a[r][3] + width*sum(a[r][k]*local[k] for k in range(3))] for r in range(3)]
    # A theater screen can be several metres wide. Scaling its bottom-edge
    # offset would put the keyboard below the floor or out of reach. Keep the
    # accepted small-window pose; use a nearby starting pose for large/far ones.
    distant = head is not None and sum((result[r][3]-head[r][3])**2 for r in range(3)) > 1.8**2
    if width > 1.6 or distant:
        if head is not None:
            direction = [a[0][3]-head[0][3], a[2][3]-head[2][3]]
            length = math.hypot(*direction)
            if length < .1:
                direction = [-head[0][2], -head[2][2]]
                length = math.hypot(*direction)
            if length < .001:
                raise ValueError('Head direction unavailable')
            dx, dz = [v/length for v in direction]
            yaw = [[-dz, 0, -dx], [0, 1, 0], [dx, 0, -dz]]
            result = [[sum(yaw[r][k]*rotation[k][c] for k in range(3)) for c in range(3)] +
                      [head[r][3] + [dx, -.55, dz][r]] for r in range(3)]
        else:
            # Tracking can be temporarily unavailable during dashboard startup.
            for r in range(3):
                result[r][3] = a[r][3] + sum(a[r][k]*[0, -.55, .337][k] for k in range(3))
        return rigid(result), .75
    return rigid(result), min(1.8, max(.45, width*profile['width_ratio']))

class Matrix(C.Structure):
    _fields_=[('m',(C.c_float*4)*3)]
class Vec2(C.Structure):
    _fields_=[('v',C.c_float*2)]
class TrackedPose(C.Structure):
    _fields_=[('matrix',Matrix),('velocity',C.c_float*3),('angular',C.c_float*3),
              ('result',C.c_int),('valid',C.c_bool),('connected',C.c_bool)]

class Overlay:
    def __init__(self):
        try:
            self.profile = json.loads(PROFILE.read_text())
        except (OSError, ValueError):
            self.profile = None
        self.lib=C.CDLL('/opt/steamvr/bin/linuxarm64/libopenvr_api.so')
        self.lib.VR_InitInternal.argtypes=[C.POINTER(C.c_int),C.c_int]
        self.lib.VR_InitInternal.restype=C.c_uint32
        error=C.c_int();self.lib.VR_InitInternal(C.byref(error),3)
        if error.value:raise RuntimeError('OpenVR overlay connection failed')
        self.lib.VR_GetGenericInterface.argtypes=[C.c_char_p,C.POINTER(C.c_int)]
        self.lib.VR_GetGenericInterface.restype=C.c_void_p
        pointer=self.lib.VR_GetGenericInterface(b'FnTable:IVROverlay_028',C.byref(error))
        if error.value or not pointer:raise RuntimeError('OpenVR overlay ABI unavailable')
        self.table=C.cast(pointer,C.POINTER(C.c_void_p))
        self.find=self.bind(0,[C.c_char_p,C.POINTER(C.c_uint64)])
        self.get_width=self.bind(23,[C.c_uint64,C.POINTER(C.c_float)])
        self.set_width=self.bind(22,[C.c_uint64,C.c_float])
        self.set_absolute=self.bind(33,[C.c_uint64,C.c_int,C.POINTER(Matrix)])
        self.get_absolute=self.bind(34,[C.c_uint64,C.POINTER(C.c_int),C.POINTER(Matrix)])
        self.coordinates=self.bind(46,[C.c_uint64,C.c_int,Vec2,C.POINTER(Matrix)])
        self.mouse_scale=self.bind(51,[C.c_uint64,C.POINTER(Vec2)])
        self.visible=self.bind(45,[C.c_uint64],C.c_bool)
        self.dashboard_visible=self.bind(68,[],C.c_bool)
    def bind(self,index,args,result=C.c_int):
        return C.CFUNCTYPE(result,*args)(self.table[index])
    def handle(self,key):
        handle=C.c_uint64()
        if self.find(key.encode(),C.byref(handle)):return None
        return handle.value
    def hide_native(self):self.bind(77,[],None)()
    def native_fallback(self,parent_key):
        parent=self.handle(parent_key)
        if not parent:return False
        native=self.handle('valve.steam.gamepadui.keyboard')
        if native and self.visible(native):return True
        show=self.bind(75,[C.c_uint64,C.c_int,C.c_int,C.c_uint32,C.c_char_p,C.c_uint32,C.c_char_p,C.c_uint64])
        return show(parent,0,0,13,b'',1024,b'',0)==0
    def close(self):self.lib.VR_ShutdownInternal()
    def geometry(self,key):
        handle=self.handle(key)
        if not handle:return None
        scale=Vec2();width=C.c_float();pose=Matrix()
        if self.mouse_scale(handle,C.byref(scale)) or self.get_width(handle,C.byref(width)):return None
        if not (0<scale.v[0]<100000 and 0<scale.v[1]<100000 and .1<width.value<20):return None
        point=Vec2();point.v[0]=scale.v[0]/2;point.v[1]=scale.v[1]/2
        if self.coordinates(handle,1,point,C.byref(pose)):return None
        return {'center':[[float(v) for v in row] for row in pose.m],
                'width':width.value,'scale':list(scale.v)}
    def head_pose(self):
        error=C.c_int()
        pointer=self.lib.VR_GetGenericInterface(b'FnTable:IVRSystem_026',C.byref(error))
        if error.value or not pointer:return None
        table=C.cast(pointer,C.POINTER(C.c_void_p))
        get=C.CFUNCTYPE(None,C.c_int,C.c_float,C.POINTER(TrackedPose),C.c_uint32)(table[12])
        poses=(TrackedPose*1)();get(1,0,poses,1)
        if not poses[0].valid or not poses[0].connected:return None
        try:return rigid([[float(v) for v in row] for row in poses[0].matrix.m])
        except ValueError:return None
    def placement(self,parent_key):
        geometry=self.geometry(parent_key)
        if not geometry:raise ValueError('Parent overlay pose unavailable')
        transform,width=keyboard_pose(geometry,self.profile,self.head_pose())
        # A user preference in metres, independent of the window's size/tilt.
        lift=float((self.profile or {}).get('height_offset_m',0))
        if not math.isfinite(lift) or abs(lift)>.25:
            raise ValueError('Invalid keyboard height offset')
        transform[1][3]+=lift
        return {'schema_version':1,'space':'standing','universe':'0',
                'transform':transform,'width_m':width}
