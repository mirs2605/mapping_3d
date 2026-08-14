import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # ─── パッケージのパス ───────────────────────────────────────────
    mapping_3d_share = get_package_share_directory('mapping-3d')
    mirs_share       = get_package_share_directory('mirs')

    rtabmap_config   = os.path.join(mapping_3d_share, 'config', 'rtabmap.yaml')
    rviz_config      = os.path.join(mapping_3d_share, 'config', 'rtabmap.rviz')
    urdf_path        = os.path.join(mirs_share, 'urdf', 'mirs.urdf.xacro')

    mirs_config_path = os.path.join(mirs_share, 'config', 'config.yaml')
    ekf_config_path  = os.path.join(mirs_share, 'config', 'ekf_params.yaml')

    # xacro で変数展開してから robot_description に渡す
    robot_desc = ParameterValue(
        Command(['xacro ', urdf_path]),
        value_type=str
    )

    # ─── Launch 引数 ────────────────────────────────────────────────
    localization_arg = DeclareLaunchArgument(
        'localization',
        default_value='false',
        description='位置推定モードで起動'
    )
    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz',
        default_value='true',
        description='RViz2起動'
    )
    use_rtabmap_viz_arg = DeclareLaunchArgument(
        'use_rtabmap_viz',
        default_value='true',
        description='rtabmap_viz (RTAB-Map専用の可視化ツール) を起動'
    )
    database_path_arg = DeclareLaunchArgument(
        'database_path',
        default_value=os.path.expanduser('~/.ros/rtabmap.db'),
        description='RTABMap の地図データベースファイルパス'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='シミュレーション時刻を使うかどうか'
    )
    esp_port_arg = DeclareLaunchArgument(
        'esp_port',
        default_value='/dev/ttyUSB0',
        description='ESP32のUSBポート'
    )
    lidar_port_arg = DeclareLaunchArgument(
        'lidar_port',
        default_value='/dev/ttyUSB1',
        description='LiDARのUSBポート'
    )

    localization    = LaunchConfiguration('localization')
    use_rviz        = LaunchConfiguration('use_rviz')
    use_rtabmap_viz = LaunchConfiguration('use_rtabmap_viz')
    database_path   = LaunchConfiguration('database_path')
    use_sim_time    = LaunchConfiguration('use_sim_time')
    esp_port        = LaunchConfiguration('esp_port')
    lidar_port      = LaunchConfiguration('lidar_port')

    # 左右カメラの共通トピック（infra1=左, infra2=右）
    left_image   = '/device/head_camera/realsense_node/infra1/image_rect_raw'
    left_info    = '/device/head_camera/realsense_node/infra1/camera_info'
    right_image  = '/device/head_camera/realsense_node/infra2/image_rect_raw'
    right_info   = '/device/head_camera/realsense_node/infra2/camera_info'

    stereo_remappings = [
        ('left/image_rect',   left_image),
        ('left/camera_info',  left_info),
        ('right/image_rect',  right_image),
        ('right/camera_info', right_info),
    ]

    # ─── 1. RealSense カメラ起動 ─────────────────────────────────────
    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(mapping_3d_share, 'launch', 'realsense.launch.py')
        )
    )

    # ─── 2. Robot State Publisher (mirs.urdf.xacro) ──────────────────
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_desc,
            'use_sim_time': use_sim_time,
        }]
    )

    # Joint State Publisher（ホイールの回転角度を配信）
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # ─── 3. ESP32 まわり（足回りオドメトリ・パラメータ・micro-ROS）────
    #  注意: odometry_publisher は C++側でTF配信をOFFにしてある前提。
    #  TFを発行するのは ekf_filter_node_local だけにする。
    odometry_node = Node(
        package='mirs',
        executable='odometry_publisher',
        name='odometry_publisher',
        output='screen',
        parameters=[mirs_config_path, {'use_sim_time': use_sim_time}]
    )

    parameter_node = Node(
        package='mirs',
        executable='parameter_publisher',
        name='parameter_publisher',
        output='screen',
        parameters=[mirs_config_path, {'use_sim_time': use_sim_time}]
    )

    micro_ros = Node(
        package='micro_ros_agent',
        executable='micro_ros_agent',
        name='micro_ros_agent',
        output='screen',
        arguments=['serial', '--dev', esp_port, '-v6']
    )

    # ─── 4. LiDARドライバ ─────────────────────────────────────────────
    sllidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('sllidar_ros2'), 'launch', 'sllidar_s1_launch.py')
        ),
        launch_arguments={'serial_port': lidar_port, 'serial_baudrate': '256000'}.items()
    )

    # ─── 5. Stereo Odometry ノード ────────────────────────────────────
    #  変更点: publish_tf を false にし、TFの発行はEKFに一本化する。
    #  代わりに /odom トピック（ESP側と衝突するため）を /odom/stereo に
    #  remap し、EKFの2つ目の入力ソースとして使う。
    #  ※ rtabmap.yaml 側の publish_tf: true は、下記 parameters で上書きする。
    stereo_odometry = Node(
        package='rtabmap_odom',
        executable='stereo_odometry',
        name='stereo_odometry',
        output='screen',
        parameters=[rtabmap_config, {
            'publish_tf': False,
            'use_sim_time': use_sim_time,
        }],
        remappings=stereo_remappings + [
            ('odom', '/odom/stereo'),
        ],
    )

    # ─── 6. EKF（センサーフュージョン。odom -> base_footprint を発行）──
    #  ※ ekf_params.yaml 側で以下を満たしていることが前提:
    #    - base_link_frame: base_footprint  (URDFの静的階層と整合させる)
    #    - world_frame: odom
    #    - publish_tf: true
    #    - odom0: /odom            (ESP32 ホイールエンコーダ)
    #    - odom1: /odom/stereo     (stereo_odometry、視覚オドメトリ)
    #  ekf_params.yaml 未調整の場合、odom1 は読み込まれず単純に無視される
    #  だけなので、まずはESP単体でTFが正しく出るかを先に確認してもよい。
    ekf_node_local = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node_local',
        output='screen',
        parameters=[ekf_config_path, {'use_sim_time': use_sim_time}],
        remappings=[('/odometry/filtered', '/odometry/local')]
    )

    # ─── 7. RTABMap ノード (SLAM モード) ─────────────────────────────
    rtabmap_slam = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        condition=UnlessCondition(localization),
        parameters=[rtabmap_config, {
            'database_path': database_path,
            'Mem/InitWMWithAllNodes': 'false',
            'use_sim_time': use_sim_time,
        }],
        remappings=stereo_remappings,
        arguments=['--delete_db_on_start'],
    )

    # ─── 8. RTABMap ノード (Localization モード) ──────────────────────
    rtabmap_localization = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        condition=IfCondition(localization),
        parameters=[rtabmap_config, {
            'database_path': database_path,
            'Mem/IncrementalMemory': 'false',
            'Mem/InitWMWithAllNodes': 'true',
            'use_sim_time': use_sim_time,
        }],
        remappings=stereo_remappings,
    )

    # ─── 9. ステレオ点群ノード ────────────────────────────────────────
    disparity_node = Node(
        package='stereo_image_proc',
        executable='disparity_node',
        name='disparity_node',
        namespace='device/head_camera',
        output='screen',
        remappings=[
            ('left/image_rect',   left_image),
            ('left/camera_info',  left_info),
            ('right/image_rect',  right_image),
            ('right/camera_info', right_info),
        ],
    )

    point_cloud_node = Node(
        package='stereo_image_proc',
        executable='point_cloud_node',
        name='point_cloud_node',
        namespace='device/head_camera',
        output='screen',
        remappings=[
            ('left/image_rect',   left_image),
            ('left/camera_info',  left_info),
            ('right/camera_info', right_info),
            ('points2',           '/rtabmap/point_cloud'),
        ],
    )

    # ─── 10. RViz2 ────────────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        condition=IfCondition(use_rviz),
        arguments=['-d', rviz_config],
    )

    # ─── 11. rtabmap_viz ────────────────────────────────────────────
    rtabmap_viz_node = Node(
        package='rtabmap_viz',
        executable='rtabmap_viz',
        name='rtabmap_viz',
        output='screen',
        condition=IfCondition(use_rtabmap_viz),
        parameters=[rtabmap_config],
        remappings=stereo_remappings,
    )

    # ─── LaunchDescription にまとめる ─────────────────────────────────
    ld = LaunchDescription()

    ld.add_action(localization_arg)
    ld.add_action(use_rviz_arg)
    ld.add_action(use_rtabmap_viz_arg)
    ld.add_action(database_path_arg)
    ld.add_action(use_sim_time_arg)
    ld.add_action(esp_port_arg)
    ld.add_action(lidar_port_arg)

    # 足回り・センサー系
    ld.add_action(odometry_node)
    ld.add_action(parameter_node)
    ld.add_action(micro_ros)
    ld.add_action(sllidar_launch)

    # ロボットモデル・状態
    ld.add_action(robot_state_publisher)
    ld.add_action(joint_state_publisher_node)

    # カメラ・視覚オドメトリ
    ld.add_action(realsense_launch)
    ld.add_action(stereo_odometry)

    # センサーフュージョン（唯一 odom->base_footprint のTFを発行する）
    ld.add_action(ekf_node_local)

    # SLAM本体・可視化
    ld.add_action(rtabmap_slam)
    ld.add_action(rtabmap_localization)
    ld.add_action(disparity_node)
    ld.add_action(point_cloud_node)
    ld.add_action(rviz_node)
    ld.add_action(rtabmap_viz_node)

    return ld
