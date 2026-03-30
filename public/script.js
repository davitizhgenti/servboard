const Servboard = {
    elements: {
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
        uptime: document.getElementById('uptime-val'),
        processList: document.getElementById('process-list'),
        macroGrid: document.getElementById('macro-grid'),
        addMacroBtn: document.getElementById('add-macro-btn'),
        macroModal: document.getElementById('macro-modal'),
        saveMacroBtn: document.getElementById('save-macro-btn'),
        cancelMacroBtn: document.getElementById('cancel-macro-btn'),
        macroName: document.getElementById('macro-name'),
        macroType: document.getElementById('macro-type'),
        macroCmd: document.getElementById('macro-cmd'),
        macroColor: document.getElementById('macro-color')
    },

    init() {
        this.bindEvents();
        this.loadMacros();
        this.startPolling();
        this.log("System Initialized");
    },

    bindEvents() {
        this.elements.runBtn.addEventListener('click', () => this.executeConsole());
        this.elements.cmdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.executeConsole();
        });

        this.elements.addMacroBtn.addEventListener('click', () => this.toggleModal(true));
        this.elements.cancelMacroBtn.addEventListener('click', () => this.toggleModal(false));
        this.elements.saveMacroBtn.addEventListener('click', () => this.saveMacro());
    },

    log(msg, isError = false) {
        const timestamp = new Date().toLocaleTimeString();
        this.elements.console.innerText += `\n[${timestamp}] ${isError ? 'ERROR: ' : ''}${msg}`;
        this.elements.console.scrollTop = this.elements.console.scrollHeight;
    },

    async updateMetrics() {
        try {
            const response = await fetch('/api/metrics');
            if (!response.ok) throw new Error('Offline');
            const data = await response.json();

            this.renderMetrics(data);
            this.renderProcesses(data.processes);

            this.elements.status.innerText = "Connected • Secure Session";
            this.elements.status.style.color = "var(--accent-secondary)";
        } catch (err) {
            this.elements.status.innerText = "Reconnecting...";
            this.elements.status.style.color = "var(--danger)";
        }
    },

    renderMetrics(data) {
        this.elements.cpuBar.style.width = `${data.cpu}%`;
        this.elements.cpuVal.innerText = `${data.cpu.toFixed(1)}%`;

        this.elements.ramBar.style.width = `${data.ram.percent}%`;
        this.elements.ramVal.innerText = `${data.ram.used} / ${data.ram.total} MB (${data.ram.percent}%)`;

        this.elements.diskBar.style.width = `${data.disk.percent}%`;
        this.elements.diskVal.innerText = `${data.disk.used} / ${data.disk.total} (${data.disk.percent}%)`;

        if (data.gpu && data.gpu.length > 0) {
            this.elements.gpuContainer.classList.remove('hidden');
            const primaryGpu = data.gpu[0];
            this.elements.gpuBar.style.width = `${primaryGpu.usage}%`;
            this.elements.gpuVal.innerText = `${primaryGpu.name}: ${primaryGpu.usage}%`;
        } else {
            this.elements.gpuContainer.classList.add('hidden');
        }
    },

    renderProcesses(processes) {
        this.elements.processList.innerHTML = processes.map(proc => `
            <tr>
                <td>${proc.pid}</td>
                <td style="color: var(--accent-primary)">${proc.name}</td>
                <td>${proc.cpu}%</td>
                <td>${proc.mem}%</td>
                <td><button class="kill-btn" onclick="Servboard.runServerCmd('kill ${proc.pid}')">Kill</button></td>
            </tr>
        `).join('');
    },

    async runServerCmd(command) {
        if (!command) return;
        this.log(`$ ${command}`);
        try {
            const res = await fetch('/api/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command })
            });
            const data = await res.json();
            if (data.output) this.log(data.output);
            if (data.error) this.log(data.error, true);
        } catch (err) {
            this.log(err.message, true);
        }
    },

    runClientScript(script) {
        this.log(`Executing Client Script...`);
        try {
            const func = new Function(script);
            func();
        } catch (err) {
            this.log(`Script Error: ${err.message}`, true);
        }
    },

    executeConsole() {
        const cmd = this.elements.cmdInput.value;
        if (cmd) {
            this.runServerCmd(cmd);
            this.elements.cmdInput.value = '';
        }
    },

    // Macro Management
    toggleModal(show) {
        this.elements.macroModal.classList.toggle('hidden', !show);
        if (show) {
            this.elements.macroName.focus();
        }
    },

    saveMacro() {
        const macro = {
            id: Date.now(),
            name: this.elements.macroName.value,
            type: this.elements.macroType.value,
            cmd: this.elements.macroCmd.value,
            color: this.elements.macroColor.value
        };

        if (!macro.name || !macro.cmd) return alert("Please fill in name and command.");

        const macros = JSON.parse(localStorage.getItem('servboard_macros') || '[]');
        macros.push(macro);
        localStorage.setItem('servboard_macros', JSON.stringify(macros));

        this.renderMacros();
        this.toggleModal(false);
        this.elements.macroName.value = '';
        this.elements.macroCmd.value = '';
    },

    deleteMacro(id) {
        const macros = JSON.parse(localStorage.getItem('servboard_macros') || '[]');
        const filtered = macros.filter(m => m.id !== id);
        localStorage.setItem('servboard_macros', JSON.stringify(filtered));
        this.renderMacros();
    },

    loadMacros() {
        this.renderMacros();
    },

    renderMacros() {
        const macros = JSON.parse(localStorage.getItem('servboard_macros') || '[]');
        this.elements.macroGrid.innerHTML = macros.map(m => `
            <div class="custom-macro-btn">
                <button onclick="Servboard.${m.type === 'server' ? 'runServerCmd' : 'runClientScript'}(\`${m.cmd.replace(/`/g, '\\`')}\`)" 
                        class="glass" style="border-color: ${m.color}">
                    ${m.name}
                </button>
                <button class="delete-macro" onclick="Servboard.deleteMacro(${m.id})">×</button>
            </div>
        `).join('');
    },

    startPolling() {
        setInterval(() => this.updateMetrics(), 2000);
        this.updateMetrics();
        this.runServerCmd('uptime -p');
    }
};

// Global helper for inline onclicks
window.runCmd = (cmd) => Servboard.runServerCmd(cmd);

document.addEventListener('DOMContentLoaded', () => Servboard.init());
