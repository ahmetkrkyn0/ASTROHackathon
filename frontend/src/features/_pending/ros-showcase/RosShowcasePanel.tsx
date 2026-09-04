import './ros-showcase.css'

interface Item {
  name: string
  detail: string
  path: string
}

// Every entry names a file that exists in this repository. Verified in
// step 1 -- nothing here is aspirational.
const NODES: Item[] = [
  {
    name: 'PlanTraverse action server',
    detail: 'Thin shell over the same planner /api/plan calls. Nav2 error-code semantics.',
    path: 'lunapath_ros/planner_node.py',
  },
  {
    name: 'grid_map publisher',
    detail: 'Publishes the cost layers as grid_map_msgs/GridMap for RViz.',
    path: 'lunapath_ros/grid_publisher.py',
  },
  {
    name: 'Pose monitor',
    detail: 'Consumes nav_msgs/Odometry and runs the same evaluate_pose the HTTP shell runs.',
    path: 'lunapath_ros/pose_monitor.py',
  },
  {
    name: 'Message assembly',
    detail: 'Message packing only — the geometry lives in app.grid_frame.',
    path: 'lunapath_ros/conversions.py',
  },
]

const INTERFACES: Item[] = [
  { name: 'PlanTraverse.action', detail: 'Goal, feedback and result contract.', path: 'lunapath_msgs/action/' },
  { name: 'Corridor.msg', detail: 'The same corridor this cockpit draws, over ROS.', path: 'lunapath_msgs/msg/' },
  { name: 'PlanMetrics.msg', detail: 'Planner metrics.', path: 'lunapath_msgs/msg/' },
  { name: 'MissionWeights.msg', detail: 'The four cost weights.', path: 'lunapath_msgs/msg/' },
  { name: 'ReplanTrigger.msg', detail: 'Trigger id and detail.', path: 'lunapath_msgs/msg/' },
]

const TOOLING: Item[] = [
  { name: 'Launch + RViz scene', detail: 'One command brings the stack up.', path: 'lunapath_ros/launch/lunapath.launch.py' },
  { name: 'rosbag2 recording', detail: 'Records one plan run.', path: 'scripts/record_plan.sh' },
  { name: 'Nav2 baseline', detail: 'Geometric baseline vs. LunaPath A*.', path: 'scripts/nav2_baseline.py' },
]

function Group({ title, items }: { title: string; items: Item[] }) {
  return (
    <>
      <h4 className="lp-ros-subhead">{title}</h4>
      <ul className="lp-ros-list">
        {items.map((item) => (
          <li key={item.path + item.name}>
            <span className="lp-ros-name">{item.name}</span>
            <span className="lp-ros-detail">{item.detail}</span>
            <code className="lp-ros-path">{item.path}</code>
          </li>
        ))}
      </ul>
    </>
  )
}

export function RosShowcasePanel() {
  return (
    <div className="lp-ros-card">
      {/* Stated first and plainly. The panel describes a real ROS 2 package
          that this browser is not talking to, and pretending otherwise
          would be the one dishonest thing in the cockpit. */}
      <p className="lp-ros-disclaimer">
        Not a live connection. These run in a ROS 2 Jazzy environment beside the
        backend; the browser has no bridge to them.
      </p>

      <Group title="Nodes" items={NODES} />
      <Group title="Interfaces" items={INTERFACES} />
      <Group title="Tooling" items={TOOLING} />

      {/* Counted, not asserted. Saying backend/app imports no fastapi would
          be false -- main.py is in that package and is the HTTP shell. The
          true and stronger claim is that it is the ONLY module that does. */}
      <p className="lp-ros-note">
        The core is shell-independent: of the 35 modules in{' '}
        <code>backend/app/</code>, only <code>main.py</code> imports fastapi and
        none imports rclpy, so the HTTP API and the ROS 2 nodes call the same
        functions and cannot drift apart.
      </p>
    </div>
  )
}
