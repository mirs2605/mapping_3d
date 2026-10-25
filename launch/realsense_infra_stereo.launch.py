"""RealSense D435i/D455 IR stereo mapping with RTAB-Map.

The left and right infrared streams are used as a stereo pair:
  /camera/infra1/image_rect_raw
  /camera/infra2/image_rect_raw
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    parameters = {
        "frame_id": "camera_link",
        "subscribe_stereo": True,
        "subscribe_odom_info": True,
        "wait_imu_to_init": False,
    }

    remappings = [
        ("left/image_rect", "/camera/infra1/image_rect_raw"),
        ("left/camera_info", "/camera/infra1/camera_info"),
        ("right/image_rect", "/camera/infra2/image_rect_raw"),
        ("right/camera_info", "/camera/infra2/camera_info"),
    ]

    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("realsense2_camera"),
                "launch",
                "rs_launch.py",
            )
        ),
        launch_arguments={
            "camera_namespace": "",
            "enable_color": "false",
            "enable_depth": "false",
            "enable_gyro": "false",
            "enable_accel": "false",
            "enable_infra1": "true",
            "enable_infra2": "true",
            "enable_sync": "true",
        }.items(),
    )

    stereo_odometry = Node(
        package="rtabmap_odom",
        executable="stereo_odometry",
        name="stereo_odometry",
        output="screen",
        parameters=[parameters],
        arguments=[LaunchConfiguration("args"), LaunchConfiguration("odom_args")],
        remappings=remappings,
    )

    rtabmap = Node(
        package="rtabmap_slam",
        executable="rtabmap",
        output="screen",
        parameters=[
            parameters,
            {
                # Mapping is intentionally odometry-only for this experiment.
                # A likelihood of 1.0 cannot be reached by the normalised
                # loop-closure hypothesis, so loop closures are rejected.
                "Rtabmap/LoopThr": "1.0",
                "RGBD/ProximityBySpace": "false",
                "RGBD/ProximityByTime": "false",
                "RGBD/CreateOccupancyGrid": "true",
            },
        ],
        arguments=["-d", LaunchConfiguration("args")],
        remappings=remappings,
    )

    rtabmap_viz = Node(
        package="rtabmap_viz",
        executable="rtabmap_viz",
        output="screen",
        parameters=[parameters, {"odometry_node_name": "stereo_odometry"}],
        remappings=remappings,
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "args",
                default_value="",
                description="Extra arguments for RTAB-Map and stereo odometry.",
            ),
            DeclareLaunchArgument(
                "odom_args",
                default_value="",
                description="Extra arguments for stereo odometry.",
            ),
            realsense_launch,
            stereo_odometry,
            rtabmap,
            rtabmap_viz,
        ]
    )
