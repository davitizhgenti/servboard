const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const PORT = process.env.PORT || 3000;

// Metric gathering functions
const getMetrics = async () => {
    const metrics = {
        cpu: 0,
        ram: { total: 0, used: 0, percent: 0 },
        disk: { total: 0, used: 0, percent: 0 },
        gpu: []
    };

    try {
        // CPU Usage (approximation using top or mpstat if available, falling back to /proc/stat)
        // For simplicity and low overhead, we'll use a 1s average if we were doing it properly, 
        // but for a quick check we'll use 'top' first line.
        const cpuRaw = await execPromise("top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'");
        metrics.cpu = parseFloat(cpuRaw.trim()) || 0;

        // RAM Usage
        const ramRaw = await execPromise("free -m | grep Mem");
        const ramParts = ramRaw.trim().split(/\s+/);
        metrics.ram.total = parseInt(ramParts[1]);
        metrics.ram.used = parseInt(ramParts[2]);
        metrics.ram.percent = Math.round((metrics.ram.used / metrics.ram.total) * 100);

        // Disk Usage
        const diskRaw = await execPromise("df -h / | tail -1");
        const diskParts = diskRaw.trim().split(/\s+/);
        metrics.disk.total = diskParts[1];
        metrics.disk.used = diskParts[2];
        metrics.disk.percent = parseInt(diskParts[4].replace('%', ''));

        // GPU Autodetection
        // 1. NVIDIA
        try {
            const nvRaw = await execPromise("nvidia-smi --query-gpu=name,utilization.gpu,utilization.memory --format=csv,noheader,nounits");
            if (nvRaw) {
                const lines = nvRaw.trim().split('\n');
                lines.forEach(line => {
                    const [name, util, mem] = line.split(', ');
                    metrics.gpu.push({ type: 'NVIDIA', name, usage: parseInt(util), memUsage: parseInt(mem) });
                });
            }
        } catch (e) {}

        // 2. Intel (GPU Busy %)
        if (metrics.gpu.length === 0) {
            try {
                const intelBusy = await execPromise("cat /sys/class/drm/card0/device/gpu_busy_percent");
                if (intelBusy) {
                    metrics.gpu.push({ type: 'Intel', name: 'Integrated Graphics', usage: parseInt(intelBusy) });
                }
            } catch (e) {}
        }

        // 3. AMD (TDP/Usage via rocm-smi if available, or thermal)
        if (metrics.gpu.length === 0) {
            try {
                const amdRaw = await execPromise("rocm-smi --showuse | grep -i '%'");
                if (amdRaw) {
                    metrics.gpu.push({ type: 'AMD', name: 'AMD Radeon', usage: parseInt(amdRaw.match(/\d+/)[0]) });
                }
            } catch (e) {}
        }

    } catch (err) {
        console.error("Error gathering metrics:", err);
    }

    return metrics;
};

const execPromise = (cmd) => {
    return new Promise((resolve, reject) => {
        exec(cmd, (error, stdout, stderr) => {
            if (error) reject(error);
            else resolve(stdout);
        });
    });
};

const server = http.createServer(async (req, res) => {
    if (req.url === '/api/metrics' && req.method === 'GET') {
        const metrics = await getMetrics();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(metrics));
        return;
    }

    if (req.url === '/api/execute' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const { command } = JSON.parse(body);
                // WARNING: In a real production environment, you MUST sanitize or restrict this.
                // For a "remote" dashboard, we'll allow it but warn the user.
                const output = await execPromise(command);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ output }));
            } catch (err) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: err.message }));
            }
        });
        return;
    }

    // Static file serving
    let filePath = path.join(__dirname, 'public', req.url === '/' ? 'index.html' : req.url);
    const extname = path.extname(filePath);
    let contentType = 'text/html';
    switch (extname) {
        case '.js': contentType = 'text/javascript'; break;
        case '.css': contentType = 'text/css'; break;
        case '.json': contentType = 'application/json'; break;
        case '.png': contentType = 'image/png'; break;
        case '.jpg': contentType = 'image/jpg'; break;
    }

    fs.readFile(filePath, (error, content) => {
        if (error) {
            if (error.code == 'ENOENT') {
                res.writeHead(404);
                res.end('File not found');
            } else {
                res.writeHead(500);
                res.end(`Server Error: ${error.code}`);
            }
        } else {
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(content, 'utf-8');
        }
    });
});

server.listen(PORT, () => {
    console.log(`Servboard running on http://localhost:${PORT}`);
});
