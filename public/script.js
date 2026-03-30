const elements = {
    cpuBar: document.getElementById('cpu-bar'),
    cpuVal: document.getElementById('cpu-val'),
    ramBar: document.getElementById('ram-bar'),
    ramVal: document.getElementById('ram-val'),
    diskBar: document.getElementById('disk-bar'),
    diskVal: document.getElementById('disk-val'),
    gpuContainer: document.getElementById('gpu-container'),
    gpuBar: document.getElementById('gpu-bar'),
    gpuVal: document.getElementById('gpu-val'),
    console: document.getElementById('console-output'),
    cmdInput: document.getElementById('cmd-input'),
    runBtn: document.getElementById('run-btn'),
    status: document.getElementById('server-status'),
    uptime: document.getElementById('uptime-val')
};

async function updateMetrics() {
    try {
        const response = await fetch('/api/metrics');
        if (!response.ok) throw new Error('Offline');
        const data = await response.json();

        // CPU
        elements.cpuBar.style.width = `${data.cpu}%`;
        elements.cpuVal.innerText = `${data.cpu.toFixed(1)}%`;

        // RAM
        elements.ramBar.style.width = `${data.ram.percent}%`;
        elements.ramVal.innerText = `${data.ram.used} / ${data.ram.total} MB (${data.ram.percent}%)`;

        // Disk
        elements.diskBar.style.width = `${data.disk.percent}%`;
        elements.diskVal.innerText = `${data.disk.used} / ${data.disk.total} (${data.disk.percent}%)`;

        // GPU
        if (data.gpu && data.gpu.length > 0) {
            elements.gpuContainer.classList.remove('hidden');
            const primaryGpu = data.gpu[0];
            elements.gpuBar.style.width = `${primaryGpu.usage}%`;
            elements.gpuVal.innerText = `${primaryGpu.name}: ${primaryGpu.usage}%`;
        } else {
            elements.gpuContainer.classList.add('hidden');
        }

        elements.status.innerText = "Connected • Secure Session";
        elements.status.style.color = "var(--accent-secondary)";

    } catch (err) {
        elements.status.innerText = "Reconnecting...";
        elements.status.style.color = "var(--danger)";
    }
}

async function runCmd(cmd) {
    const command = cmd || elements.cmdInput.value;
    if (!command) return;

    elements.console.innerText += `\n$ ${command}\nExecuting...`;
    elements.console.scrollTop = elements.console.scrollHeight;

    try {
        const res = await fetch('/api/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        const data = await res.json();
        
        if (data.output) {
            elements.console.innerText += `\n${data.output}`;
        } else if (data.error) {
            elements.console.innerText += `\nError: ${data.error}`;
        }
    } catch (err) {
        elements.console.innerText += `\nConnection Error: ${err.message}`;
    }
    
    elements.console.scrollTop = elements.console.scrollHeight;
    elements.cmdInput.value = '';
}

elements.runBtn.addEventListener('click', () => runCmd());
elements.cmdInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') runCmd();
});

// Update every 2 seconds
setInterval(updateMetrics, 2000);
updateMetrics();

// Initial Uptime call
runCmd('uptime -p').then(() => {
    // We'll just hijack the console for the first uptime
});
