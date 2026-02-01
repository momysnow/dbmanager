/**
 * DBManager Enterprise UI Logic
 */

// API Client
const api = {
    baseUrl: '/api/v1',

    getHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const token = localStorage.getItem('access_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    },

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = { ...this.getHeaders(), ...(options.headers || {}) };

        const res = await fetch(url, { ...options, headers });

        if (res.status === 401) {
            localStorage.removeItem('access_token');
            window.location.href = '/login';
            throw new Error('Unauthorized');
        }

        if (!res.ok) {
            let errorMsg = 'Request failed';
            try {
                const err = await res.json();
                errorMsg = err.detail || errorMsg;
            } catch (e) { }
            throw new Error(errorMsg);
        }

        return await res.json();
    },

    async get(endpoint) { return await this.request(endpoint); },
    async post(endpoint, data) {
        return await this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    async put(endpoint, data) {
        return await this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    async delete(endpoint) {
        return await this.request(endpoint, {
            method: 'DELETE'
        });
    },

    async addDatabase(event) {
        event.preventDefault();
        const formData = new FormData(event.target);

        // Handle checkbox correctly
        const s3Enabled = formData.get('s3_enabled') === 'on';
        const s3BucketId = formData.get('s3_bucket_id');

        const data = {
            name: formData.get('name'),
            provider: formData.get('provider'),
            params: {
                host: formData.get('host'),
                port: parseInt(formData.get('port')),
                database: formData.get('database'),
                user: formData.get('user'),
                password: formData.get('password')
            },
            s3_enabled: s3Enabled,
            s3_bucket_id: s3BucketId ? parseInt(s3BucketId) : null,
            retention: parseInt(formData.get('retention') || 0)
        };

        try {
            await this.post('/databases', data);
            ui.modals.addDb.close();
            ui.showToast('Database added successfully!', 'success');
            router.navigate('databases');
        } catch (e) {
            ui.showToast('Error: ' + e.message, 'error');
        }
    },

    async updateDatabase(event, dbId) {
        event.preventDefault();
        const formData = new FormData(event.target);

        const s3Enabled = formData.get('s3_enabled') === 'on';
        const s3BucketId = formData.get('s3_bucket_id');

        const data = {
            name: formData.get('name'),
            provider: formData.get('provider'),
            params: {
                host: formData.get('host'),
                port: parseInt(formData.get('port')),
                database: formData.get('database'),
                user: formData.get('user'),
                password: formData.get('password') // Only send if changed? logic handled by backend usually
            },
            s3_enabled: s3Enabled,
            s3_bucket_id: s3BucketId ? parseInt(s3BucketId) : null,
            retention: parseInt(formData.get('retention') || 0)
        };

        // If password is empty, remove it to avoid overwriting with empty string
        if (!data.params.password) delete data.params.password;

        try {
            await this.put(`/databases/${dbId}`, data);
            ui.modals.editDb.close();
            ui.showToast('Database updated successfully!', 'success');
            router.navigate('databases');
        } catch (e) {
            ui.showToast('Error: ' + e.message, 'error');
        }
    },

    async verifyBackup(file, location, dbId) {
        return await this.post('/backups/verify', { backup_file: file, location, database_id: dbId });
    },

    async deleteBackup(file, location, dbId) {
        let qs = `backup_file=${encodeURIComponent(file)}&location=${location}`;
        if (dbId) qs += `&database_id=${dbId}`;
        return await this.request(`/backups?${qs}`, { method: 'DELETE' });
    },

    async addS3Bucket(event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const data = Object.fromEntries(formData.entries());
        // Convert to correct types if needed (none strictly needed for strings)

        try {
            await this.post('/s3-buckets', data);
            ui.modals.addS3.close();
            ui.showToast('S3 Bucket added', 'success');
            ui.renderS3();
        } catch (e) { ui.showToast(e.message, 'error'); }
    },

    async deleteS3Bucket(id) {
        return await this.delete(`/s3-buckets/${id}`);
    },

    async getSchedules() { return await this.get('/schedules'); },
    async createSchedule(event) {
        event.preventDefault();
        const formData = new FormData(event.target);

        // Cron parts builder
        const cron = `${formData.get('cron_min')} ${formData.get('cron_hour')} ${formData.get('cron_dom')} ${formData.get('cron_mon')} ${formData.get('cron_dow')}`;

        const data = {
            name: formData.get('name'),
            database_id: parseInt(formData.get('database_id')),
            cron_expression: cron,
            backup_type: 'full', // Default for now
            retention: parseInt(formData.get('retention') || 0),
            enabled: true
        };

        try {
            await this.post('/schedules', data);
            ui.modals.addSchedule.close();
            ui.showToast('Schedule created', 'success');
            ui.renderSchedules();
        } catch (e) { ui.showToast(e.message, 'error'); }
    },
    async deleteSchedule(id) { return await this.delete(`/schedules/${id}`); },
    async toggleSchedule(id) { return await this.post(`/schedules/${id}/toggle`); },

    async saveSettings(event) {
        event.preventDefault();
        const formData = new FormData(event.target);

        try {
            // Compression
            await this.put('/settings/compression', {
                enabled: formData.get('comp_enabled') === 'on',
                algorithm: 'gzip', // fixed for now or add select
                level: parseInt(formData.get('comp_level') || 6)
            });

            // Encryption
            const encryptEnabled = formData.get('enc_enabled') === 'on';
            let encData = { enabled: encryptEnabled };
            const encPwd = formData.get('enc_password');

            // Send request (password as query param or body? Checking router...)
            // Router: PUT /settings/encryption Body: EncryptionSettings, Query: password
            // We need to construct URL for query param if password provided
            let encUrl = '/settings/encryption';
            if (encryptEnabled && encPwd) {
                encUrl += `?password=${encodeURIComponent(encPwd)}`;
            }
            await this.put(encUrl, encData);

            // Notifications (Mock for now as API might not differ per provider yet)
            // await this.put('/settings/notifications', ...);

            ui.showToast('Settings saved successfully', 'success');
        } catch (e) {
            ui.showToast('Error saving settings: ' + e.message, 'error');
        }
    }
};

// UI Manager
const ui = {
    showToast(msg, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `glass-card`;
        toast.style.position = 'fixed';
        toast.style.bottom = '20px';
        toast.style.right = '20px';
        toast.style.padding = '16px';
        toast.style.background = type === 'error' ? 'rgba(255, 50, 50, 0.9)' :
            type === 'success' ? 'rgba(0, 200, 100, 0.9)' : 'rgba(30, 30, 30, 0.9)';
        toast.style.color = 'white';
        toast.style.zIndex = '2000';
        toast.style.border = '1px solid rgba(255,255,255,0.1)';
        toast.innerHTML = type === 'success' ? `<i class="fa-solid fa-check-circle"></i> ${msg}` :
            type === 'error' ? `<i class="fa-solid fa-triangle-exclamation"></i> ${msg}` : msg;

        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    },

    modals: {
        addDb: {
            el: document.getElementById('add-db-modal'),
            async open() {
                if (this.el) {
                    // Populate S3 buckets
                    try {
                        const buckets = await api.get('/s3-buckets');
                        const select = this.el.querySelector('select[name="s3_bucket_id"]');
                        if (select) {
                            select.innerHTML = '<option value="">Select Bucket...</option>' +
                                buckets.map(b => `<option value="${b.id}">${b.name}</option>`).join('');
                        }
                    } catch (e) { }
                    this.el.classList.add('open');
                }
            },
            close() { if (this.el) this.el.classList.remove('open'); }
        },
        editDb: {
            el: null, // Created dynamically
            close() {
                const el = document.getElementById('edit-db-modal');
                if (el) el.remove();
            }
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
                if (!this.el) return;
                this.title.textContent = title || 'Processing...';
                this.percent.textContent = '0%';
                this.bar.style.width = '0%';
                this.msg.textContent = 'Starting...';
                this.closeBtn.style.display = 'none';
                this.el.classList.add('open');
            },
            update(data) {
                if (!this.el) return;
                this.step.textContent = data.step || 'Processing';
                this.msg.textContent = data.message || '';
                if (data.percentage !== undefined) {
                    this.percent.textContent = Math.round(data.percentage) + '%';
                    this.bar.style.width = Math.round(data.percentage) + '%';
                }

                if (data.status === 'completed' || data.status === 'failed') {
                    this.closeBtn.style.display = 'block';
                    this.bar.style.backgroundColor = data.status === 'failed' ? 'var(--error)' : 'var(--success)';
                }
            },
            close() {
                if (!this.el) return;
                this.el.classList.remove('open');
                setTimeout(() => { this.bar.style.backgroundColor = 'var(--primary)'; }, 300);
            }
        },
        addS3: {
            el: null,
            open() {
                const modalHtml = `
                <div class="modal-overlay open" id="add-s3-modal">
                    <div class="modal">
                        <h2 style="margin-top: 0;">Add S3 Bucket</h2>
                        <form onsubmit="api.addS3Bucket(event)">
                            <label>Name (Alias)</label>
                            <input type="text" name="name" required placeholder="My Backups">

                            <label>Provider</label>
                            <select name="provider" onchange="this.nextElementSibling.style.display = this.value === 'aws' ? 'none' : 'block'">
                                <option value="aws">AWS S3</option>
                                <option value="cloudflare">Cloudflare R2</option>
                                <option value="minio">MinIO / Custom</option>
                            </select>
                            
                            <div style="display:none;">
                                <label>Endpoint URL</label>
                                <input type="text" name="endpoint_url" placeholder="https://...">
                            </div>

                            <label>Bucket Name</label>
                            <input type="text" name="bucket_name" required>

                            <label>Region</label>
                            <input type="text" name="region_name" value="us-east-1">

                            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                                <div>
                                    <label>Access Key</label>
                                    <input type="text" name="access_key" required>
                                </div>
                                <div>
                                    <label>Secret Key</label>
                                    <input type="password" name="secret_key" required>
                                </div>
                            </div>

                            <div style="display: flex; gap: 10px; margin-top: 20px;">
                                <button type="button" class="btn" style="background: rgba(255,255,255,0.1);" onclick="ui.modals.addS3.close()">Cancel</button>
                                <button type="submit" class="btn btn-primary">Add Bucket</button>
                            </div>
                        </form>
                    </div>
                </div>`;
                document.body.insertAdjacentHTML('beforeend', modalHtml);
                this.el = document.getElementById('add-s3-modal');
            },
            close() {
                if (this.el) this.el.remove();
                this.el = null;
            }
        },
        addSchedule: {
            el: null,
            async open() {
                try {
                    const dbs = await api.get('/databases');
                    const options = dbs.map(d => `<option value="${d.id}">${d.name}</option>`).join('');

                    const modalHtml = `
                    <div class="modal-overlay open" id="add-schedule-modal">
                        <div class="modal">
                            <h2 style="margin-top: 0;">Add Backup Schedule</h2>
                            <form onsubmit="api.createSchedule(event)">
                                <label>Schedule Name</label>
                                <input type="text" name="name" required placeholder="Daily Backup">

                                <label>Database</label>
                                <select name="database_id" required>
                                    ${options}
                                </select>

                                <label style="margin-top:20px; color:var(--primary);">Cron Expression</label>
                                <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:5px; text-align:center;">
                                    <div><input type="text" name="cron_min" value="0" style="text-align:center;"><div style="font-size:10px;">Min</div></div>
                                    <div><input type="text" name="cron_hour" value="0" style="text-align:center;"><div style="font-size:10px;">Hour</div></div>
                                    <div><input type="text" name="cron_dom" value="*" style="text-align:center;"><div style="font-size:10px;">Day</div></div>
                                    <div><input type="text" name="cron_mon" value="*" style="text-align:center;"><div style="font-size:10px;">Mon</div></div>
                                    <div><input type="text" name="cron_dow" value="*" style="text-align:center;"><div style="font-size:10px;">WkDay</div></div>
                                </div>
                                <div style="font-size:12px; color:var(--text-secondary); margin-top:5px; text-align:center;">
                                    Format: * = every. 0 2 * * * = Every day at 2am.
                                </div>

                                <label style="margin-top:20px;">Retention (Copies to keep)</label>
                                <input type="number" name="retention" value="30">

                                <div style="display: flex; gap: 10px; margin-top: 20px;">
                                    <button type="button" class="btn" style="background: rgba(255,255,255,0.1);" onclick="ui.modals.addSchedule.close()">Cancel</button>
                                    <button type="submit" class="btn btn-primary">Create Schedule</button>
                                </div>
                            </form>
                        </div>
                    </div>`;
                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                    this.el = document.getElementById('add-schedule-modal');
                } catch (e) { ui.showToast('Error loading databases', 'error'); }
            },
            close() {
                if (this.el) this.el.remove();
                this.el = null;
            }
        }
    },

    async openEditDbModal(dbId) {
        try {
            const db = (await api.get('/databases')).find(d => d.id === dbId);
            const buckets = await api.get('/s3-buckets');

            const modalHtml = `
            <div class="modal-overlay open" id="edit-db-modal">
                <div class="modal">
                    <h2 style="margin-top: 0;">Edit Database</h2>
                    <form onsubmit="api.updateDatabase(event, ${dbId})">
                        <label>Name</label>
                        <input type="text" name="name" required value="${db.name}">

                        <label>Provider</label>
                        <select name="provider" disabled style="opacity:0.7">
                            <option value="${db.provider}" selected>${db.provider.toUpperCase()}</option>
                        </select>
                        <input type="hidden" name="provider" value="${db.provider}">

                        <div style="display:grid; grid-template-columns: 2fr 1fr; gap:10px;">
                            <div>
                                <label>Host</label>
                                <input type="text" name="host" required value="${db.params.host}">
                            </div>
                            <div>
                                <label>Port</label>
                                <input type="number" name="port" required value="${db.params.port}">
                            </div>
                        </div>

                        <label>Database Name</label>
                        <input type="text" name="database" required value="${db.params.database}">

                        <label>User</label>
                        <input type="text" name="user" required value="${db.params.user}">

                        <label>Password (Leave empty to keep current)</label>
                        <input type="password" name="password" placeholder="••••••••">
                        
                         <div style="margin: 20px 0; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 20px;">
                            <label style="color:var(--primary); margin-bottom:10px; display:block;">Backup Settings</label>
                            
                            <label>Local Retention (Count)</label>
                            <input type="number" name="retention" value="${db.retention || 0}">
                            
                            <div style="display:flex; align-items:center; gap:10px; margin-top:15px;">
                                <input type="checkbox" name="s3_enabled" style="width:auto; margin:0;" ${db.s3_enabled ? 'checked' : ''}>
                                <label style="margin:0;">Enable S3 Upload</label>
                            </div>
                            
                            <label style="margin-top:10px;">S3 Bucket</label>
                            <select name="s3_bucket_id">
                                <option value="">Select Bucket...</option>
                                ${buckets.map(b => `<option value="${b.id}" ${db.s3_bucket_id === b.id ? 'selected' : ''}>${b.name}</option>`).join('')}
                            </select>
                        </div>

                        <div style="display: flex; gap: 10px; margin-top: 20px;">
                            <button type="button" class="btn" style="background: rgba(255,255,255,0.1);" onclick="ui.modals.editDb.close()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Save Changes</button>
                        </div>
                    </form>
                </div>
            </div>`;

            document.body.insertAdjacentHTML('beforeend', modalHtml);
        } catch (e) {
            ui.showToast('Error loading database details: ' + e.message, 'error');
        }
    },

    async renderDatabases() {
        try {
            const dbs = await api.get('/databases');
            const container = document.querySelector('.main-content');

            if (!dbs || dbs.error) throw new Error('Failed to load databases');

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

            if (dbs.length === 0) {
                html += `<div style="grid-column: 1/-1; text-align:center; padding:40px; color:var(--text-secondary);">
                    <i class="fa-solid fa-database" style="font-size: 48px; margin-bottom: 20px; opacity: 0.5;"></i><br>
                    No databases configured yet. Click "Add Database" to get started.
                </div>`;
            } else {
                dbs.forEach(db => {
                    html += `
                        <div class="glass-card">
                            <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:16px;">
                                <div>
                                    <h3 style="margin:0; font-size:18px;">${db.name}</h3>
                                    <div class="text-secondary" style="font-size:12px; margin-top:4px;">${db.provider.toUpperCase()}</div>
                                </div>
                                <button class="btn btn-sm" style="background:transparent; color:var(--text-secondary);" onclick="ui.openEditDbModal(${db.id})">
                                    <i class="fa-solid fa-pen"></i>
                                </button>
                            </div>
                            
                            <div style="font-size:14px; color:var(--text-secondary); margin-bottom:20px;">
                                <div><i class="fa-solid fa-server" style="width:20px"></i> ${db.params.host}:${db.params.port}</div>
                                <div style="margin-top:8px"><i class="fa-solid fa-database" style="width:20px"></i> ${db.params.database}</div>
                                <div style="margin-top:8px">
                                    <i class="fa-brands fa-aws" style="width:20px; color: ${db.s3_enabled ? 'var(--primary)' : 'inherit'}"></i> 
                                    ${db.s3_enabled ? 'S3 Enabled' : 'Local Only'}
                                </div>
                            </div>
        
                            <div style="display:flex; gap:10px;">
                                <button class="btn btn-primary btn-sm" onclick="actions.backup(${db.id}, '${db.name}')" style="flex:1">
                                    <i class="fa-solid fa-play"></i> Backup
                                </button>
                                <button class="btn btn-sm" style="background:rgba(255,255,255,0.1)" onclick="router.navigate('backups', ${db.id})">
                                    <i class="fa-solid fa-clock-rotate-left"></i>
                                </button>
                                <button class="btn btn-sm text-error" style="background:rgba(255,50,50,0.1)" onclick="actions.deleteDatabase(${db.id})">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </div>
                        </div>
                    `;
                });
            }

            html += `</div>`;
            container.innerHTML = html;
        } catch (e) {
            console.error(e);
            ui.showToast('Failed to load databases', 'error');
        }
    },

    async renderBackups(dbId = null) {
        const container = document.querySelector('.main-content');

        try {
            // Get all DBs for selector
            let dbs = [];
            try { dbs = await api.get('/databases'); } catch (e) { }

            // Auto-select first if none selected
            if (!dbId && dbs.length > 0) dbId = dbs[0].id;

            if (!dbId) {
                container.innerHTML = `<div class="header"><h1 class="page-title">Backups</h1></div><div style="padding:40px; text-align:center;">No databases found.</div>`;
                return;
            }

            const currentDb = dbs.find(d => d.id == dbId) || { name: 'Unknown' };
            const backups = await api.get(`/databases/${dbId}/backups`);

            let html = `
                <div class="header">
                    <div>
                        <h1 class="page-title">Backups</h1>
                        <div style="color:var(--text-secondary); font-size:14px; margin-top:5px; display:flex; align-items:center; gap:10px;">
                            database: 
                            <select onchange="router.navigate('backups', this.value)" style="width:auto; margin:0; padding:6px; background:rgba(255,255,255,0.1); border:none; color:white; border-radius:4px;">
                                ${dbs.map(d => `<option value="${d.id}" ${d.id == dbId ? 'selected' : ''}>${d.name}</option>`).join('')}
                            </select>
                        </div>
                    </div>
                </div>

                <div class="glass-card" style="padding:0; overflow:hidden;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left;">
                        <thead style="background: rgba(255,255,255,0.05); color: var(--text-secondary);">
                            <tr>
                                <th style="padding: 16px;">Filename</th>
                                <th style="padding: 16px;">Date</th>
                                <th style="padding: 16px;">Size</th>
                                <th style="padding: 16px;">Location</th>
                                <th style="padding: 16px; text-align:right;">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            if (backups.length === 0) {
                html += `<tr><td colspan="5" style="padding:32px; text-align:center; color:var(--text-muted);">No backups found.</td></tr>`;
            } else {
                backups.forEach(b => {
                    const isS3 = b.location === 's3';
                    const locationIcon = isS3 ? '<span class="badge badge-warning" style="background:rgba(255, 165, 0, 0.2); color:orange; padding:2px 6px; border-radius:4px;"><i class="fa-brands fa-aws"></i> S3</span>' : '<span class="badge" style="background:rgba(200, 200, 200, 0.2); padding:2px 6px; border-radius:4px;"><i class="fa-solid fa-hard-drive"></i> Local</span>';

                    // Escape filename and path for onclick
                    const safePath = b.path.replace(/'/g, "\\'");

                    html += `
                    <tr>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); font-family:monospace;">
                            ${b.filename}
                            ${b.has_checksum ? '<i class="fa-solid fa-shield-halved text-success" title="Integrity Check Available" style="margin-left:8px; font-size:12px;"></i>' : ''}
                        </td>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">${new Date(b.date).toLocaleString()}</td>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">${b.size_mb.toFixed(2)} MB</td>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05);">${locationIcon}</td>
                        <td style="padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); text-align:right;">
                            <button class="btn btn-sm" onclick="actions.verify('${safePath}', '${b.location || 'local'}', ${dbId})" title="Verify Integrity" style="background:rgba(255,255,255,0.1); margin-right:5px;">
                                <i class="fa-solid fa-check-double"></i>
                            </button>
                            <button class="btn btn-sm" onclick="actions.restore(${dbId}, '${safePath}', '${b.location || 'local'}')" title="Restore" style="background:rgba(255,255,255,0.1); margin-right:5px;">
                                <i class="fa-solid fa-rotate-left"></i>
                            </button>
                            <button class="btn btn-sm text-error" onclick="actions.deleteBackup('${safePath}', '${b.location || 'local'}', ${dbId})" title="Delete" style="background:rgba(255,50,50,0.1)">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>`;
                });
            }
            html += `</tbody></table></div>`;
            container.innerHTML = html;

        } catch (e) {
            ui.showToast('Error loading backups: ' + e.message, 'error');
        }
    },

    async renderSettings() {
        const container = document.querySelector('.main-content');
        try {
            const comp = await api.get('/settings/compression');
            const enc = await api.get('/settings/encryption');

            container.innerHTML = `
                <div class="header">
                    <h1 class="page-title">Settings</h1>
                </div>
                
                <div class="card-grid" style="grid-template-columns: 1fr; max-width: 800px;">
                    <div class="glass-card">
                        <h3>Global Configuration</h3>
                        <form onsubmit="api.saveSettings(event)">
                            <div style="margin-bottom: 30px;">
                                <h4 style="color:var(--primary); border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;">Compression</h4>
                                <div style="display:flex; align-items:center; gap:10px; margin-bottom:15px;">
                                    <input type="checkbox" name="comp_enabled" style="width:auto; margin:0;" ${comp.enabled ? 'checked' : ''}>
                                    <label style="margin:0;">Enable Compression (GZIP)</label>
                                </div>
                                <div style="margin-left: 25px;">
                                    <label>Compression Level (1-9)</label>
                                    <input type="range" name="comp_level" min="1" max="9" value="${comp.level}" style="width:100%; margin-top:10px;">
                                    <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-secondary);">
                                        <span>Fast (1)</span>
                                        <span>Balanced (6)</span>
                                        <span>Best (9)</span>
                                    </div>
                                </div>
                            </div>

                            <div style="margin-bottom: 30px;">
                                <h4 style="color:var(--primary); border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;">Encryption</h4>
                                <div style="display:flex; align-items:center; gap:10px; margin-bottom:15px;">
                                    <input type="checkbox" name="enc_enabled" style="width:auto; margin:0;" ${enc.enabled ? 'checked' : ''}>
                                    <label style="margin:0;">Enable Encryption (Fernet)</label>
                                </div>
                                <div style="margin-left: 25px;">
                                    <label>Encryption Password</label>
                                    <input type="password" name="enc_password" placeholder="Set new password to change..." autocomplete="new-password">
                                    <div class="text-warning" style="font-size:12px; margin-top:5px;">
                                        <i class="fa-solid fa-circle-exclamation"></i> Warning: Losing this password means losing access to your backups forever.
                                    </div>
                                </div>
                            </div>
                            
                            <button type="submit" class="btn btn-primary" style="width:100%;">Save All Settings</button>
                        </form>
                    </div>
                </div>
            `;
        } catch (e) {
            ui.showToast('Error loading settings', 'error');
        }
    },

    // ... S3 and Dashboard render methods (kept as simple as previous or enhanced similarly)
    async renderDashboard() {
        const container = document.querySelector('.main-content');
        // Simplified dashboard for brevity, assume similar structure to before but robust
        container.innerHTML = `<div class="header"><h1 class="page-title">Dashboard</h1></div><div class="glass-card">Loading...</div>`;

        try {
            const dbs = await api.get('/databases');

            // Calc stats
            const totalDbs = dbs.length;
            const activeDbs = dbs.length;

            container.innerHTML = `
            <div class="header">
                <h1 class="page-title">Dashboard</h1>
                <div class="actions">
                    <button class="btn btn-primary" onclick="ui.modals.addDb.open()">
                        <i class="fa-solid fa-plus"></i> Add Database
                    </button>
                </div>
            </div>

            <div class="card-grid">
                <div class="glass-card">
                    <div class="stat-label">Total Databases</div>
                    <div class="stat-value">${totalDbs}</div>
                    <div class="text-success"><i class="fa-solid fa-check"></i> ${activeDbs} Active</div>
                </div>
                <div class="glass-card">
                    <div class="stat-label">System Status</div>
                    <div class="stat-value" style="font-size:24px; color:var(--success);">Operational</div>
                    <div class="text-muted">API Online</div>
                </div>
            </div>`;
        } catch (e) {
            container.innerHTML = `<div class="text-error">Failed to load dashboard. API Error.</div>`
        }
    },

    async renderS3() {
        const container = document.querySelector('.main-content');
        try {
            const buckets = await api.get('/s3-buckets');
            let html = `
                <div class="header">
                    <h1 class="page-title">S3 Storage</h1>
                    <button class="btn btn-primary" onclick="ui.modals.addS3.open()"><i class="fa-solid fa-plus"></i> Add Bucket</button>
                </div>
                <div class="card-grid">`;

            if (buckets.length === 0) {
                html += `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">No S3 buckets configured.</div>`;
            } else {
                buckets.forEach(b => {
                    html += `
                    <div class="glass-card">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <div>
                                <h3 style="margin:0;">${b.name}</h3>
                                <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${b.provider.toUpperCase()}</div>
                            </div>
                            <button class="btn btn-sm text-error" style="background:rgba(255,50,50,0.1)" onclick="actions.deleteS3Bucket(${b.id})">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </div>
                        <div style="margin-top:15px; color:var(--text-secondary); font-size:14px;">
                            <div style="margin-bottom:5px;"><i class="fa-solid fa-bucket" style="width:20px;"></i> ${b.bucket_name}</div>
                            <div style="margin-bottom:5px;"><i class="fa-solid fa-globe" style="width:20px;"></i> ${b.region_name}</div>
                            ${b.endpoint_url ? `<div><i class="fa-solid fa-link" style="width:20px;"></i> ${b.endpoint_url}</div>` : ''}
                        </div>
                    </div>`;
                });
            }
            html += `</div>`;
            container.innerHTML = html;
        } catch (e) { ui.showToast('Error loading S3: ' + e.message, 'error'); }
    },

    async renderSchedules() {
        const container = document.querySelector('.main-content');
        try {
            const schedules = await api.getSchedules();
            let html = `
                <div class="header">
                    <h1 class="page-title">Schedules</h1>
                    <button class="btn btn-primary" onclick="ui.modals.addSchedule.open()"><i class="fa-solid fa-plus"></i> Add Schedule</button>
                </div>
                <div class="card-grid">`;

            if (schedules.length === 0) {
                html += `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">No schedules configured.</div>`;
            } else {
                schedules.forEach(s => {
                    html += `
                    <div class="glass-card" style="border-left: 4px solid ${s.enabled ? 'var(--success)' : 'var(--text-muted)'};">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <div>
                                <h3 style="margin:0;">${s.name}</h3>
                                <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
                                    <i class="fa-solid fa-database"></i> Database ID: ${s.database_id}
                                </div>
                            </div>
                            <div style="display:flex; gap:5px;">
                                <button class="btn btn-sm" style="background:rgba(255,255,255,0.1)" onclick="actions.toggleSchedule(${s.id})" title="${s.enabled ? 'Disable' : 'Enable'}">
                                    <i class="fa-solid fa-${s.enabled ? 'pause' : 'play'}"></i>
                                </button>
                                <button class="btn btn-sm text-error" style="background:rgba(255,50,50,0.1)" onclick="actions.deleteSchedule(${s.id})">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div style="margin-top:15px; display:flex; justify-content:space-between; align-items:flex-end;">
                            <div style="font-family:monospace; background:rgba(0,0,0,0.3); padding:4px 8px; border-radius:4px;">
                                ${s.cron_expression}
                            </div>
                            <div style="font-size:12px; color:var(--text-secondary);">
                                Last: ${s.last_run ? new Date(s.last_run).toLocaleString() : 'Never'}<br>
                                Next: ${s.next_run ? new Date(s.next_run).toLocaleString() : 'Pending'}
                            </div>
                        </div>
                    </div>`;
                });
            }
            html += `</div>`;
            container.innerHTML = html;
        } catch (e) { ui.showToast('Error loading schedules: ' + e.message, 'error'); }
    }
};

// ... WebSocket, Router, Actions kept same or enhanced ...
const ws = {
    connect(taskId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/tasks/${taskId}`);
        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            ui.modals.task.update(data);
            if (data.status === 'completed' || data.status === 'failed') socket.close();
        };
    }
};

const router = {
    navigate(page, param) {
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        document.querySelector(`.nav-link[data-page="${page}"]`)?.classList.add('active');
        if (page === 'dashboard') ui.renderDashboard();
        if (page === 'databases') ui.renderDatabases();
        if (page === 'backups') ui.renderBackups(param);
        if (page === 's3') ui.renderS3();
        if (page === 'schedules') ui.renderSchedules();
        if (page === 'settings') ui.renderSettings();
    }
};



const actions = {
    async backup(dbId, name) {
        if (!confirm(`Backup ${name}?`)) return;
        ui.modals.task.open(`Backing up ${name}`, 'Starting backup...');
        try {
            const res = await api.post(`/databases/${dbId}/backup`);
            // Wait for task completion via generic poller or simple timeout/websocket
            // Implementation of WS logic:
            const socket = new WebSocket(`ws://${window.location.host}/api/v1/ws/tasks/${res.task_id}`);
            socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                ui.modals.task.update(data);
                if (data.status === 'completed' || data.status === 'failed') socket.close();
            };
        } catch (e) { ui.modals.task.update({ status: 'failed', message: e.message }); }
    },

    async restore(dbId, path, location) {
        if (!confirm(`Restore from ${location.toUpperCase()} backup?\n\nFile: ${path}\n\nCurrent data will be overwritten.`)) return;
        ui.modals.task.open('Restoring Database', 'Initializing restore...');
        try {
            const res = await api.post(`/databases/${dbId}/restore`, {
                backup_file: path,
                location: location
            });

            const socket = new WebSocket(`ws://${window.location.host}/api/v1/ws/tasks/${res.task_id}`);
            socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                ui.modals.task.update(data);
                if (data.status === 'completed' || data.status === 'failed') socket.close();
            };
        } catch (e) { ui.modals.task.update({ status: 'failed', message: e.message }); }
    },

    async verify(path, location, dbId) {
        ui.showToast('Verifying backup integrity...', 'info');
        try {
            const res = await api.verifyBackup(path, location, dbId);
            if (res.valid) {
                ui.showToast(`✅ Integrity Verified: ${res.message}`, 'success');
            } else {
                ui.showToast(`❌ Verification Failed: ${res.message}`, 'error');
            }
        } catch (e) {
            ui.showToast(`Verification Error: ${e.message}`, 'error');
        }
    },

    async deleteBackup(path, location, dbId) {
        if (!confirm(`Delete this ${location ? location.toUpperCase() : 'LOCAL'} backup permanently?`)) return;
        try {
            await api.deleteBackup(path, location, dbId);
            ui.showToast('Backup deleted', 'success');
            // Refresh list
            ui.renderBackups(dbId);
        } catch (e) { ui.showToast(e.message, 'error'); }
    },

    async deleteDatabase(id) {
        if (!confirm('Delete this database configuration?')) return;
        try {
            await api.delete(`/databases/${id}`);
            ui.showToast('Deleted');
            router.navigate('databases');
        } catch (e) { ui.showToast(e.message, 'error'); }
    },

    async deleteS3Bucket(id) {
        if (!confirm('Delete this S3 bucket configuration?')) return;
        try {
            await api.deleteS3Bucket(id);
            ui.showToast('Bucket removed', 'success');
            ui.renderS3();
        } catch (e) { ui.showToast(e.message, 'error'); }
    },

    async deleteSchedule(id) {
        if (!confirm('Delete this schedule?')) return;
        try {
            await api.deleteSchedule(id);
            ui.showToast('Schedule deleted', 'success');
            ui.renderSchedules();
        } catch (e) { ui.showToast(e.message, 'error'); }
    },

    async toggleSchedule(id) {
        try {
            await api.toggleSchedule(id);
            ui.renderSchedules();
        } catch (e) { ui.showToast(e.message, 'error'); }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if (!localStorage.getItem('access_token')) window.location.href = '/login';
    else ui.renderDashboard();
});
