import os
import launch_ros.actions
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # パッケージのディレクトリを取得
    pkg_dir = get_package_share_directory('mapping-3d')
    config_file = os.path.join(pkg_dir, 'config', 'realsense.yaml')

    # Launch引数の定義
    # 注意: この名前を 'use_rviz' のような汎用的な名前にすると、この
    # launch ファイルをどこかから include して launch_arguments で値を
    # 渡した際に、呼び出し元(親)側の同名 LaunchConfiguration まで
    # 上書きしてしまう事故が起きやすいため、あえて固有の名前にしている。
    # use_rviz_arg = DeclareLaunchArgument(
    #     'realsense_use_rviz',
    #     default_value='false',
    #     description='RViz2を起動して左右IR画像/点群を可視化するかどうか'
    # )

    # RealSense D435ノード
    # ステレオカメラとして動作させ、左右赤外線(infra1/infra2)画像をpublishする。
    # 深度・カラーストリームは無効（本番のステレオカメラ相当の構成）
    realsense_node = launch_ros.actions.Node(
        package='realsense2_camera',
        namespace='device/head_camera',
        name='realsense_node',
        executable='realsense2_camera_node',
        parameters=[config_file],
        emulate_tty=True,
        output='screen'
    )

    # RViz2ノード（オプション）
    # rviz_node = launch_ros.actions.Node(
    #     package='rviz2',
    #     executable='rviz2',
    #     name='rviz2',
    #     arguments=['-d', os.path.join(pkg_dir, 'config', 'realsense_pointcloud.rviz')],
    #     condition=IfCondition(LaunchConfiguration('realsense_use_rviz')),
    #     output='screen'
    # )

    return LaunchDescription([
        # use_rviz_arg,
        realsense_node,
        # rviz_node,
    ])
