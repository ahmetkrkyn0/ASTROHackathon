# ROS 2 Kurulumu — LunaPath

**Dağıtım: Jazzy Jalisco** (LTS, destek May 2029, Ubuntu 24.04).
Kilted Kaiju Aralık 2026'da EOL; Lyrical Luth (May 2026) henüz çok yeni ve
`grid_map` / Nav2 kapsaması olgunlaşmadı. (Spec §4.2)

Depo Windows'ta geliştiriliyor; Python çekirdeği (FastAPI + A*) Windows'ta
kalır, yalnızca ROS düğümü Linux'ta koşar.

## Seçilen seçenek
A (WSL2)

## Seçenek A — WSL2
(kurulum komutları: bkz. Faz 4 planı Task 1 Step 1)

## Seçenek B — Docker
    docker build -t lunapath-ros:jazzy -f docker/ros2-jazzy.Dockerfile .
    docker run -it --rm -v "$(pwd)":/workspace lunapath-ros:jazzy

## Çekirdeği ROS düğümlerine görünür kılmak
`lunapath_ros`, `backend/app` içindeki saf fonksiyonları import eder:

    export PYTHONPATH="/workspace/backend:$PYTHONPATH"

## Derleme
    source /opt/ros/jazzy/setup.bash
    colcon build --packages-select lunapath_msgs lunapath_ros
    source install/setup.bash

## Kurulu Nav2 ComputePathToPose hata kodları

Output of `ros2 interface show grid_map_msgs/msg/GridMap` (WSL Ubuntu-24.04, ROS 2 Jazzy, captured 2026-08-29):

```
# Header (time and frame)
std_msgs/Header header
	builtin_interfaces/Time stamp
		int32 sec
		uint32 nanosec
	string frame_id

# Grid map header
GridMapInfo info
	float64 resolution
	float64 length_x
	float64 length_y
	geometry_msgs/Pose pose
		Point position
			float64 x
			float64 y
			float64 z
		Quaternion orientation
			float64 x 0
			float64 y 0
			float64 z 0
			float64 w 1

# Grid map layer names.
string[] layers

# Grid map basic layer names (optional). The basic layers
# determine which layers from `layers` need to be valid
# in order for a cell of the grid map to be valid.
string[] basic_layers

# Grid map data.
std_msgs/Float32MultiArray[] data
	MultiArrayLayout  layout        #
		#
		#
		#
		#
		#
		MultiArrayDimension[] dim #
			string label   #
			uint32 size    #
			uint32 stride  #
		uint32 data_offset        #
	float32[]         data          #

# Row start index (default 0).
uint16 outer_start_index

# Column start index (default 0).
uint16 inner_start_index
```

Output of `ros2 interface show nav2_msgs/action/ComputePathToPose` (same install, same capture):

```
#goal definition
geometry_msgs/PoseStamped goal
	std_msgs/Header header
		builtin_interfaces/Time stamp
			int32 sec
			uint32 nanosec
		string frame_id
	Pose pose
		Point position
			float64 x
			float64 y
			float64 z
		Quaternion orientation
			float64 x 0
			float64 y 0
			float64 z 0
			float64 w 1
geometry_msgs/PoseStamped start
	std_msgs/Header header
		builtin_interfaces/Time stamp
			int32 sec
			uint32 nanosec
		string frame_id
	Pose pose
		Point position
			float64 x
			float64 y
			float64 z
		Quaternion orientation
			float64 x 0
			float64 y 0
			float64 z 0
			float64 w 1
string planner_id
bool use_start # If false, use current robot pose as path start, if true, use start above instead
---
#result definition

# Error codes
# Note: The expected priority order of the errors should match the message order
uint16 NONE=0
uint16 UNKNOWN=200
uint16 INVALID_PLANNER=201
uint16 TF_ERROR=202
uint16 START_OUTSIDE_MAP=203
uint16 GOAL_OUTSIDE_MAP=204
uint16 START_OCCUPIED=205
uint16 GOAL_OCCUPIED=206
uint16 TIMEOUT=207
uint16 NO_VALID_PATH=208

nav_msgs/Path path
	std_msgs/Header header
		builtin_interfaces/Time stamp
			int32 sec
			uint32 nanosec
		string frame_id
	geometry_msgs/PoseStamped[] poses
		std_msgs/Header header
			builtin_interfaces/Time stamp
				int32 sec
				uint32 nanosec
			string frame_id
		Pose pose
			Point position
				float64 x
				float64 y
				float64 z
			Quaternion orientation
				float64 x 0
				float64 y 0
				float64 z 0
				float64 w 1
builtin_interfaces/Duration planning_time
	int32 sec
	uint32 nanosec
uint16 error_code
string error_msg
---
#feedback definition
```

NOTE for whoever writes `lunapath_msgs/action/PlanTraverse.action` (Task 3): the
installed Nav2 error code set is exactly the ten values the Faz 4 plan's R9
revision already lists (NONE=0, UNKNOWN=200, INVALID_PLANNER=201, TF_ERROR=202,
START_OUTSIDE_MAP=203, GOAL_OUTSIDE_MAP=204, START_OCCUPIED=205,
GOAL_OCCUPIED=206, TIMEOUT=207, NO_VALID_PATH=208) plus a `string error_msg`
result field alongside `uint16 error_code`, and a `bool use_start` goal field
("If false, use current robot pose as path start, if true, use start above
instead" — matches the plan's requirement that PlanTraverse only supports
use_start=true, rejecting false with TF_ERROR).

## Task 3: PlanTraverse hata kodu diff'i (Nav2 ile karşılaştırma)

Command (WSL Ubuntu-24.04, ROS 2 Jazzy, `lunapath_msgs` derlendikten sonra, captured 2026-08-29):

```
diff <(ros2 interface show nav2_msgs/action/ComputePathToPose | grep -E '^uint16 [A-Z_]+=' | sort) \
     <(ros2 interface show lunapath_msgs/action/PlanTraverse  | grep -E '^uint16 [A-Z_]+=' | sort)
```

Output: empty (no diff, exit code 0). `lunapath_msgs/action/PlanTraverse`'in on
hata kodu (`NONE=0`, `UNKNOWN=200`, `INVALID_PLANNER=201`, `TF_ERROR=202`,
`START_OUTSIDE_MAP=203`, `GOAL_OUTSIDE_MAP=204`, `START_OCCUPIED=205`,
`GOAL_OCCUPIED=206`, `TIMEOUT=207`, `NO_VALID_PATH=208`) kurulu
`nav2_msgs/action/ComputePathToPose` ile birebir aynı — ne eksik ne fazla kod
var, hiçbir isim farklı sayı taşımıyor.

## Task 7: Foxglove bridge kuruldu mu?

Atlandı. `sudo apt install -y ros-jazzy-foxglove-bridge` bu otomasyon ortamında
etkileşimli `sudo` parolası olmadığı için çalıştırılamıyor. Kabul kriteri zaten
`lunapath_ros/config/lunapath.rviz` (Task 7 Step 2) ile karşılanıyor — RViz2
konfigürasyonu `moon_map` Fixed Frame'i, `/lunapath/grid_map`'i (`elevation`
katmanı) ve bir `nav_msgs/Path` display'ini içeriyor, log tabanlı doğrulamayla
(config parse/plugin-load hatası yok, çökme yok) teyit edildi. İnteraktif
`sudo` erişimi olan biri isterse şunu çalıştırabilir:

```bash
sudo apt install -y ros-jazzy-foxglove-bridge
ros2 launch foxglove_bridge foxglove_bridge_launch.xml
```

## Space ROS ve taşınabilirlik

LunaPath'in planlama çekirdeği saf Python fonksiyonlarından oluşur ve I/O'dan
ayrıktır (`backend/app/`; içinde tek bir `import rclpy` yoktur — Faz 4 kabul
kriteri bunu doğrular). ROS 2 kabuğu (`lunapath_ros`) bu çekirdeği bir action
server olarak servis eder. Space ROS, ROS 2 API'siyle uyumlu olduğu için bu
kabuk, uçuş nitelemesi gereken bir bağlama taşındığında yeniden yazılmaz —
yalnızca yeniden derlenir.

Aynı gerekçe FastAPI kabuğu için de geçerlidir: iki kabuk aynı çekirdeği
çağırır, hiçbiri diğerinin yerine geçmez.
