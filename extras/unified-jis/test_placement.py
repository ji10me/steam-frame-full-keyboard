import math
import unittest
from frame_jis_vr import keyboard_pose, native_profile, rigid


class Placement(unittest.TestCase):
    def test_stock_style_is_tilted_and_forward_without_inheriting_scale(self):
        parent = {'center': [[.5,0,0,0],[0,.5,0,1],[0,0,.5,-1]], 'width':2,'scale':[1600,800]}
        pose, width = keyboard_pose(parent)
        self.assertAlmostEqual(width,.75)
        self.assertAlmostEqual(pose[1][3],.46)
        self.assertAlmostEqual(pose[2][3],-.663)
        self.assertAlmostEqual(math.degrees(math.atan2(pose[1][2],pose[2][2])),50)
        for column in range(3):
            self.assertAlmostEqual(sum(pose[r][column]**2 for r in range(3)),1)

    def test_measured_reference_reproduces_world_pose_and_width(self):
        parent = {'center': [[.5,0,0,.2],[0,.5,0,1.4],[0,0,.5,-1.2]], 'width':2,'scale':[1600,900]}
        angle=math.radians(-50)
        desired=[[1,0,0,.2],[0,math.cos(angle),-math.sin(angle),.9],[0,math.sin(angle),math.cos(angle),-.8]]
        native={'center':[[desired[r][c]*([.75,.75,.375][c]) if c<3 else desired[r][c] for c in range(4)] for r in range(3)], 'width':1,'scale':[1280,420]}
        profile=native_profile(parent,native)
        pose,width=keyboard_pose(parent,profile)
        for r in range(3):
            for c in range(4):self.assertAlmostEqual(pose[r][c],desired[r][c])
        self.assertAlmostEqual(width,.75)
        # Parent translation/scale change carries the relative starting pose.
        parent['center'][0][3]+=.5
        moved,_=keyboard_pose(parent,profile)
        self.assertAlmostEqual(moved[0][3],desired[0][3]+.5)

    def test_degenerate_and_mirrored_transforms_are_rejected(self):
        for transform in ([[0,0,0,0]]*3, [[1,0,0,0],[0,-1,0,0],[0,0,1,0]]):
            with self.assertRaises(ValueError):rigid(transform)

    def test_theater_keyboard_stays_near_head_and_above_floor(self):
        parent={'center':[[1,0,0,-2.4],[0,1,0,1.4],[0,0,1,-2.3]],'width':2.8,'scale':[1920,1080]}
        head=[[1,0,0,.1],[0,1,0,1.4],[0,0,1,-.6]]
        pose,width=keyboard_pose(parent,head=head)
        self.assertAlmostEqual(width,.75)
        self.assertAlmostEqual(pose[1][3],.85)
        self.assertAlmostEqual(math.hypot(pose[0][3]-.1,pose[2][3]+.6),1)
        self.assertAlmostEqual(math.degrees(math.asin(pose[1][2])),50)
        # Its front normal points from the screen towards the user.
        self.assertGreater(sum(pose[r][2]*(head[r][3]-pose[r][3]) for r in (0,2)),0)

    def test_tracking_unavailable_does_not_scale_large_panel_offset(self):
        parent={'center':[[1,0,0,0],[0,1,0,1.4],[0,0,1,-2]],'width':2.8,'scale':[1920,1080]}
        pose,width=keyboard_pose(parent)
        self.assertAlmostEqual(width,.75)
        self.assertAlmostEqual(pose[1][3],.85)


if __name__=='__main__':unittest.main()
