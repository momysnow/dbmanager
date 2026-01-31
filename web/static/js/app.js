/**
 * DBManager Enterprise UI Logic
 */

// API Client
const api = {
    baseUrl: '/api/v1',

    async get(endpoint) {
        const res = await fetch(`${this.baseUrl}${endpoint}`);
        return await res.json();
    },

    async post(endpoint, data) {
        const res = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Request failed');
        }
        return await res.json();
    },

    async addDatabase(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const data = {
            name: formData.get('name'),
            provider: formData.get('provider'),
            params: {
                host: formData.get('host'),
                port: parseInt(formData.get('port')),
                database: formData.get('database'),
                user: formData.get('user'),
                password: formData.get('password') // ConfigManager will encrypt this
            }
        };

        try {
            await this.post('/databases', data);
            ui.modals.addDb.close();
            alert('Database added successfully!');
            router.navigate('databases'); // Refresh list
        } catch (e) {
            alert('Error: ' + e.message);
        }
    }
};

// UI Manager
const ui = {
    modals: {
        addDb: {
            el: document.getElementById('add-db-modal'),
            open() { this.el.classList.add('open'); },
            close() { this.el.classList.remove('open'); }
        },
        task: {
            el: document.getElementById('task-modal'),
            title: document.getElementById('task-title'),
            step: document.getElementById('task-step'),
            percent: document.getElementById('task-percent'),
            bar: document.getElementById('task-bar'),
            msg: document.getElementById('task-message'),
            closeBtn: document.getElementById('task-close-btn'),

            open(title) {
                this.title.textContent = title || 'Processing...';
                this.percent.textContent = '0%';
                this.bar.style.width = '0%';
                this.msg.textContent = 'Starting...';
                this.closeBtn.style.display = 'none';
                this.el.classList.add('open');
            },
            update(data) {
                this.step.textContent = data.step || 'Processing';
                this.msg.textContent = data.message || '';
                if (data.percentage !== undefined) {
                    this.percent.textContent = Math.round(data.percentage) + '%';
                    this.bar.style.width = Math.round(data.percentage) + '%';
                }

                if (data.status === 'completed' || data.status === 'failed') {
                    this.closeBtn.style.display = 'block';
                    if (data.status === 'failed') {
                        this.bar.style.backgroundColor = 'var(--error)';
                    } else {
                        this.bar.style.backgroundColor = 'var(--success)';
                    }
                }
            },
            close() {
                this.el.classList.remove('open');
                // Reset bar color
                setTimeout(() => { this.bar.style.backgroundColor = 'var(--primary)'; }, 300);
            }
        }
    },

    async renderDashboard() {
        const dbList = await api.get('/databases');
        document.getElementById('stats-total-db').textContent = dbList.length;
        document.getElementById('stats-active-db').textContent = dbList.length; // Placeholder logic

        // Populate activity table (mockup for now)
        const tbody = document.getElementById('activity-list');
        tbody.innerHTML = ''; // clear loading

        // Mock data
        const activities = [
            { time: 'Just now', db: 'Production DB', action: 'Backup', status: 'Success', duration: '45s' },
            { time: '2h ago', db: 'Staging DB', action: 'Backup', status: 'Success', duration: '12s' }
        ];

        activities.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">${item.time}</td>
                <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 500;">${item.db}</td>
                <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">${item.action}</td>
                <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);"><span class="badge badge-success">${item.status}</span></td>
                <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); color: var(--text-muted);">${item.duration}</td>
            `;
            tbody.appendChild(tr);
        });
    },

    async renderDatabases() {
        const dbs = await api.get('/databases');
        const container = document.querySelector('.main-content');

        // Rebuild main content for Databases View
        let html = `
            <div class="header">
                <h1 class="page-title">Databases</h1>
                <div class="actions">
                    <button class="btn btn-primary" onclick="ui.modals.addDb.open()">
                        <i class="fa-solid fa-plus"></i> Add Database
                    </button>
                </div>
            </div>
            <div class="card-grid">
        `;

        dbs.forEach(db => {
            html += `
                <div class="glass-card">
                    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:16px;">
                        <div>
                            <h3 style="margin:0; font-size:18px;">${db.name}</h3>
                            <div class="text-secondary" style="font-size:12px; margin-top:4px;">${db.provider}</div>
                        </div>
                        <span class="badge badge-success">Active</span>
                    </div>
                    
                    <div style="font-size:14px; color:var(--text-secondary); margin-bottom:20px;">
                        <div><i class="fa-solid fa-server" style="width:20px"></i> ${db.params.host}:${db.params.port}</div>
                        <div style="margin-top:8px"><i class="fa-solid fa-database" style="width:20px"></i> ${db.params.database}</div>
                    </div>

                    <div style="display:flex; gap:10px;">
                        <button class="btn btn-primary btn-sm" onclick="actions.backup(${db.id}, '${db.name}')">
                            <i class="fa-solid fa-play"></i> Backup
                        </button>
                        <button class="btn btn-sm" style="background:rgba(255,255,255,0.1)" onclick="router.navigate('backups', ${db.id})">
                            <i class="fa-solid fa-clock-rotate-left"></i> History
                        </button>
                    </div>
                </div>
            `;
        });

        if (dbs.length === 0) {
            html += `<div style="grid-column: 1/-1; text-align:center; padding:40px; color:var(--text-secondary);">No databases configured yet.</div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
    },

    async renderBackups(dbId = null) {
        const container = document.querySelector('.main-content');
        let dbs = [];

        if (!dbId) {
            // If no specific DB selected, show selector or list all (simplified: show selector first)
            dbs = await api.get('/databases');
            if (dbs.length > 0 && !dbId) dbId = dbs[0].id;
        } else {
            // We need DB info for title
            const allDbs = await api.get('/databases');
            dbs = allDbs; // Keep all for selector
        }

        if (!dbId) {
            container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--text-secondary);">No databases available. Add one first.</div>`;
            return;
        }

        // Fetch backups for selected DB
        let backups = [];
        try {
            backups = await api.get(`/databases/${dbId}/backups`);
        } catch (e) {
            console.error("Failed to fetch backups", e);
        }

        const currentDb = dbs.find(d => d.id == dbId) || { name: 'Unknown' };

        let html = `
            <div class="header">
                <div>
                    <h1 class="page-title">Backups</h1>
                    <div style="color:var(--text-secondary); font-size:14px; margin-top:5px;">
                        Viewing backups for: 
                        <select onchange="router.navigate('backups', this.value)" style="display:inline-block; width:auto; margin:0; padding:4px 8px; background:rgba(255,255,255,0.1); border:none;">
                            ${dbs.map(d => `<option value="${d.id}" ${d.id == dbId ? 'selected' : ''}>${d.name}</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="actions">
                    <button class="btn btn-primary" onclick="actions.backup(${dbId}, '${currentDb.name}')">
                        <i class="fa-solid fa-play"></i> Backup Now
                    </button>
                </div>
            </div>
            
            <div class="glass-card" style="padding:0; overflow:hidden;">
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead style="background: rgba(255,255,255,0.05); color: var(--text-secondary);">
                        <tr>
                            <th style="padding: 16px;">Filename</th>
                            <th style="padding: 16px;">Date</th>
                            <th style="padding: 16px;">Size</th>
                            <th style="padding: 16px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        if (backups.length === 0) {
            html += `<tr><td colspan="4" style="padding:32px; text-align:center; color:var(--text-muted);">No backups found for this database.</td></tr>`;
        } else {
            backups.forEach(b => {
                const date = new Date(b.date).toLocaleString();
                html += `
                    <tr>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); font-family:monospace;">${b.filename}</td>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">${date}</td>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">${b.size_mb.toFixed(2)} MB</td>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">
                            <button class="btn btn-sm" onclick="actions.restore(${dbId}, '${b.path}')" title="Restore">
                                <i class="fa-solid fa-rotate-left"></i>
                            </button>
                            <button class="btn btn-sm text-error" onclick="actions.deleteBackup('${b.path}')" title="Delete">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });
        }

        html += `</tbody></table></div>`;
        container.innerHTML = html;
    }
};

// WebSocket Handler
const ws = {
    connect(taskId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/tasks/${taskId}`);

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            ui.modals.task.update(data);

            if (data.status === 'completed' || data.status === 'failed') {
                socket.close();
                // Refresh data if needed
                if (data.status === 'completed') {
                    // Slight delay to allow user to see 100%
                }
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            ui.modals.task.update({ status: 'failed', message: 'Connection lost' });
        };
    }
};

// Router
const router = {
    navigate(page, param = null) {
        // Update nav
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        document.querySelector(`.nav-link[data-page="${page}"]`)?.classList.add('active');

        // Route
        if (page === 'dashboard') {
            ui.renderDashboard();
        } else if (page === 'databases') {
            ui.renderDatabases();
        } else if (page === 'backups') {
            ui.renderBackups(param);
        } else {
            const container = document.querySelector('.main-content');
            container.innerHTML = `<div style="padding:40px; text-align:center;"><h2>🚧 Work in Progress</h2><p>The ${page} page comes in the next update.</p></div>`;
        }
    }
};

// Actions
const actions = {
    async backup(dbId, dbName) {
        if (!confirm(`Start backup for ${dbName}?`)) return;

        ui.modals.task.open(`Backing up ${dbName}`);

        try {
            const res = await api.post(`/databases/${dbId}/backup`);
            // Connect to WebSocket using the returned task_id
            ws.connect(res.task_id);
        } catch (e) {
            ui.modals.task.update({ status: 'failed', message: e.message });
        }
    },

    async restore(dbId, backupPath) {
        if (!confirm('⚠️ WARNING: This will overwrite the current database. Are you sure?')) return;

        ui.modals.task.open('Restoring Database');

        try {
            const res = await api.post(`/databases/${dbId}/restore`, { backup_file: backupPath });
            ws.connect(res.task_id);
        } catch (e) {
            ui.modals.task.update({ status: 'failed', message: e.message });
        }
    },

    async deleteBackup(backupPath) {
        if (!confirm('Delete this backup file?')) return;
        try {
            await Promise.resolve(); // Implement delete API call here
            // Note: Delete API might need to be added or called differently
            // For now assuming we just refresh
            alert('Delete feature coming soon to API');
        } catch (e) {
            alert('Error: ' + e.message);
        }
    }
};

// Init
document.addEventListener('DOMContentLoaded', () => {
    ui.renderDashboard();
});
