// Socket.IO connection
const socket = io();

// D3.js plot variables
let svg, xScale, yScale, plotWidth, plotHeight;

// ==================== Socket.IO Events ====================

socket.on('connect', () => {
    console.log('Connected to server');
    updateConnectionStatus(true);
    addLog('Connected to navigation server', 'success');
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    updateConnectionStatus(false);
    addLog('Disconnected from server', 'error');
});

socket.on('status_update', (data) => {
    updateRobotStatus(data);
});

socket.on('success', (data) => {
    addLog(data.message, 'success');
});

socket.on('error', (data) => {
    addLog(data.message, 'error');
});

socket.on('warning', (data) => {
    addLog(data.message, 'warning');
});

socket.on('status', (data) => {
    addLog(data.message, 'info');
});

socket.on('nav_log', (data) => {
    addLog('[NAV] ' + data.message, 'info');
});

// ==================== UI Update Functions ====================

function updateConnectionStatus(connected) {
    const badge = document.getElementById('connection-status');
    if (connected) {
        badge.textContent = 'Connected';
        badge.classList.remove('disconnected');
        badge.classList.add('connected');
    } else {
        badge.textContent = 'Disconnected';
        badge.classList.remove('connected');
        badge.classList.add('disconnected');
    }
}

function updateRobotStatus(status) {
    // Update pose
    if (status.pose) {
        document.getElementById('pos-x').textContent = status.pose.x.toFixed(2) + ' m';
        document.getElementById('pos-y').textContent = status.pose.y.toFixed(2) + ' m';
        document.getElementById('heading').textContent = status.pose.heading_deg.toFixed(1) + '\u00B0';
    }

    // Update waypoint
    document.getElementById('waypoint').textContent =
        `${status.current_waypoint} / ${status.total_waypoints}`;

    // Update track status with color coding
    const trackBadge = document.getElementById('track-status');
    trackBadge.textContent = status.track_status;
    trackBadge.style.color = '#ffffff';

    if (status.track_status === 'TRACK_FINISHED') {
        trackBadge.style.backgroundColor = '#BDDB94';
    } else if (status.track_status === 'ABORTED' || status.track_status === 'TRACK_ABORTED' || status.track_status === 'TRACK_FAILED') {
        trackBadge.style.backgroundColor = '#ef4444';
    } else {
        trackBadge.style.background = 'linear-gradient(135deg, #BDDB94 100%, #d97706 100%)';
    }

    // Update filter convergence
    const filterBadge = document.getElementById('filter-converged');
    filterBadge.textContent = status.filter_converged ? 'YES' : 'NO';
    if (status.filter_converged) {
        filterBadge.style.color = '#ffffff';
        filterBadge.style.backgroundColor = '#BDDB94';
    } else {
        filterBadge.style.color = '#ffffff';
        filterBadge.style.backgroundColor = '#ef4444';
    }

    // Update button states
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');

    if (status.navigation_running) {
        btnStart.disabled = true;
        btnStop.disabled = false;
    } else {
        btnStart.disabled = false;
        btnStop.disabled = true;
    }
}

function addLog(message, type = 'info') {
    const logContainer = document.getElementById('log-container');
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${timestamp}] ${message}`;
    logContainer.appendChild(entry);

    // Auto-scroll to bottom
    logContainer.scrollTop = logContainer.scrollHeight;

    // Limit to 100 entries
    while (logContainer.children.length > 100) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// ==================== Control Functions ====================

function startNavigation() {
    socket.emit('start_navigation');
    addLog('Sending start command...', 'info');
}

function stopNavigation() {
    socket.emit('stop_navigation');
    addLog('Sending stop command...', 'info');
}

function emergencyStop() {
    if (confirm('EMERGENCY STOP - Are you sure?')) {
        socket.emit('emergency_stop');
        addLog('EMERGENCY STOP ACTIVATED', 'error');
    }
}

// ==================== Waypoint Plot (D3.js) ====================

function initializePlot() {
    const container = d3.select('#plot-container');
    const containerNode = container.node();
    const containerWidth = containerNode.clientWidth;
    const containerHeight = containerNode.clientHeight;

    const margin = { top: 20, right: 20, bottom: 40, left: 60 };
    plotWidth = containerWidth - margin.left - margin.right;
    plotHeight = containerHeight - margin.top - margin.bottom;

    svg = container.append('svg')
        .attr('width', containerWidth)
        .attr('height', containerHeight)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Initial scales
    xScale = d3.scaleLinear().range([0, plotWidth]);
    yScale = d3.scaleLinear().range([plotHeight, 0]);

    // Add axes
    svg.append('g')
        .attr('class', 'x-axis')
        .attr('transform', `translate(0,${plotHeight})`)
        .style('color', '#0294D0');

    svg.append('g')
        .attr('class', 'y-axis')
        .style('color', '#0294D0');

    // Add grid
    svg.append('g')
        .attr('class', 'grid-y')
        .style('stroke', '#374151')
        .style('stroke-opacity', 0.3)
        .style('stroke-dasharray', '2,2');

    svg.append('g')
        .attr('class', 'grid-x')
        .attr('transform', `translate(0,${plotHeight})`)
        .style('stroke', '#374151')
        .style('stroke-opacity', 0.3)
        .style('stroke-dasharray', '2,2');

    // Add axis labels
    svg.append('text')
        .attr('class', 'x-label')
        .attr('text-anchor', 'middle')
        .attr('x', plotWidth / 2)
        .attr('y', plotHeight + 35)
        .style('fill', '#0294D0')
        .text('X (meters)');

    svg.append('text')
        .attr('class', 'y-label')
        .attr('text-anchor', 'middle')
        .attr('transform', 'rotate(-90)')
        .attr('x', -plotHeight / 2)
        .attr('y', -45)
        .style('fill', '#0294D0')
        .text('Y (meters)');
}

function updatePlot(data) {
    if (!svg) return;

    const waypoints = data.waypoints || [];
    const robot = data.robot;
    const currentIndex = data.current_index || 0;

    if (waypoints.length === 0) return;

    // Update scales
    const xExtent = d3.extent(waypoints, d => d.x);
    const yExtent = d3.extent(waypoints, d => d.y);

    const xPadding = (xExtent[1] - xExtent[0]) * 0.1 || 1;
    const yPadding = (yExtent[1] - yExtent[0]) * 0.1 || 1;

    xScale.domain([xExtent[0] - xPadding, xExtent[1] + xPadding]);
    yScale.domain([yExtent[0] - yPadding, yExtent[1] + yPadding]);

    // Update axes
    svg.select('.x-axis').call(d3.axisBottom(xScale).ticks(5));
    svg.select('.y-axis').call(d3.axisLeft(yScale).ticks(5));

    // Update grid
    svg.select('.grid-y')
        .call(d3.axisLeft(yScale)
            .ticks(5)
            .tickSize(-plotWidth)
            .tickFormat(''));

    svg.select('.grid-x')
        .call(d3.axisBottom(xScale)
            .ticks(5)
            .tickSize(-plotHeight)
            .tickFormat(''));

    // Update waypoint markers
    const circles = svg.selectAll('.waypoint')
        .data(waypoints, d => d.index);

    circles.enter()
        .append('circle')
        .attr('class', 'waypoint')
        .merge(circles)
        .attr('cx', d => xScale(d.x))
        .attr('cy', d => yScale(d.y))
        .attr('r', d => d.index === currentIndex ? 8 : 5)
        .attr('fill', d => {
            if (d.index === currentIndex) return '#3b82f6';
            if (d.index < currentIndex) return '#BDDB94';
            return '#ef4444';
        })
        .attr('stroke', d => d.index === currentIndex ? 'white' : 'none')
        .attr('stroke-width', 2)
        .style('cursor', 'pointer')
        .append('title')
        .text(d => `Waypoint ${d.index}\nX: ${d.x.toFixed(2)}\nY: ${d.y.toFixed(2)}`);

    circles.exit().remove();

    // Update robot position
    if (robot && robot.x !== undefined && robot.y !== undefined) {
        let robotMarker = svg.select('.robot-marker');

        if (robotMarker.empty()) {
            robotMarker = svg.append('g').attr('class', 'robot-marker');

            robotMarker.append('circle')
                .attr('r', 10)
                .attr('fill', '#FBB24B')
                .attr('stroke', 'white')
                .attr('stroke-width', 2);

            robotMarker.append('path')
                .attr('class', 'heading-arrow')
                .attr('fill', 'white');
        }

        robotMarker.attr('transform',
            `translate(${xScale(robot.x)}, ${yScale(robot.y)})`);

        if (robot.heading !== undefined) {
            const arrowPath = `M 0,-12 L 4,0 L 0,8 L -4,0 Z`;
            robotMarker.select('.heading-arrow')
                .attr('d', arrowPath)
                .attr('transform', `rotate(${-robot.heading * 180 / Math.PI})`);
        }
    }
}

function fetchPlotData() {
    fetch('/plot_data')
        .then(response => response.json())
        .then(data => {
            updatePlot(data);
        })
        .catch(error => {
            console.error('Error fetching plot data:', error);
        });
}

// ==================== Camera Feed ====================

function initializeCameraFeed() {
    const cameraFeed = document.getElementById('camera-feed');
    const cameraOverlay = document.getElementById('camera-overlay');

    cameraFeed.addEventListener('load', () => {
        if (cameraOverlay) {
            cameraOverlay.style.display = 'none';
        }
    });

    cameraFeed.addEventListener('error', () => {
        if (cameraOverlay) {
            cameraOverlay.style.display = 'block';
            cameraOverlay.innerHTML = '<div class="camera-info">Camera feed unavailable</div>';
        }
    });
}

// ==================== Initialization ====================

document.addEventListener('DOMContentLoaded', () => {
    initializeCameraFeed();
    initializePlot();

    // Fetch plot data every second
    setInterval(fetchPlotData, 1000);
    fetchPlotData();

    addLog('Dashboard loaded', 'info');
});
