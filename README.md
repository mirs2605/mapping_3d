# mapping_3d

RealSense D435/D435i/D455の左右IRカメラをステレオ入力として、RTAB-Mapで3Dマッピングを行うROS 2 Jazzyパッケージです。

この実験構成では、RGB、深度センサ、IMU、ループクロージャを使用しません。左右IR画像からステレオVisual Odometryを計算し、その積算結果だけで地図を構築します。40m以遠では視差が小さくなるため、距離精度は別途評価してください。

## 起動

ワークスペースをビルドしてセットアップを読み込みます。

```bash
colcon build --symlink-install --packages-select mapping_3d
source install/setup.bash
```

起動します。

```bash
ros2 launch mapping_3d realsense_infra_stereo.launch.py
```

使用する主なトピックは次の通りです。

```text
/camera/infra1/image_rect_raw    左IR画像
/camera/infra2/image_rect_raw    右IR画像
/camera/infra1/camera_info       左CameraInfo
/camera/infra2/camera_info       右CameraInfo
/odom                            ステレオオドメトリ
```

ループクロージャを無効化しているため、長距離走行ではドリフトが累積します。`rtabmap_viz`では、ステレオ特徴点、オドメトリ品質、地図のドリフトを確認してください。

画像が出ているか確認するには、別ターミナルで次を実行します。

```bash
ros2 topic hz /camera/infra1/image_rect_raw
ros2 topic hz /camera/infra2/image_rect_raw
ros2 topic echo /camera/infra1/camera_info --once
```

データベースを削除して実験を開始する場合は、次のように引数を渡します。

```bash
ros2 launch mapping_3d realsense_infra_stereo.launch.py \
  args:="--delete_db_on_start"
```
