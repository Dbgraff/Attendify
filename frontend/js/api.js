const API_BASE = '/api';

let token = localStorage.getItem('access_token');

export const setToken = (newToken) => {
    token = newToken;
    if (token) localStorage.setItem('access_token', token);
    else localStorage.removeItem('access_token');
};

const fetchWithAuth = async (url, options = {}) => {
    const headers = { ...options.headers };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    console.debug(`[fetchWithAuth] ${options.method || 'GET'} ${url}`);
    try {
        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const text = await response.text();
            console.error(`[fetchWithAuth] HTTP ${response.status} for ${url}`, text);
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 200)}`);
        }
        return response;
    } catch (err) {
        console.error(`[fetchWithAuth] Network error for ${url}:`, err);
        console.error(err.stack);
        throw err;
    }
};

export const api = {
    async login(username, password) {
        const res = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (!res.ok) throw new Error('Login failed');
        const data = await res.json();
        setToken(data.access_token);
        return data;
    },

    async me() {
        const res = await fetchWithAuth(`${API_BASE}/me`);
        if (!res.ok) throw new Error('Failed to get user info');
        return res.json();
    },

    async getGroups() {
        const res = await fetchWithAuth(`${API_BASE}/groups`);
        if (!res.ok) throw new Error('Failed to fetch groups');
        return res.json(); // массив объектов { code, is_curator }
    },

    async getStudents(groupCode) {
        if (!groupCode) return []; // не отправляем запрос, если группа не выбрана
        const res = await fetchWithAuth(`${API_BASE}/students?group=${encodeURIComponent(groupCode)}`);
        if (!res.ok) throw new Error('Failed to fetch students');
        return res.json();
    },

    async addStudent(groupCode, fullName, notes = '', subgroup = 0) {
        const res = await fetchWithAuth(`${API_BASE}/students`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group: groupCode, full_name: fullName, notes, subgroup })
        });
        if (!res.ok) throw new Error('Failed to add student');
        return res.json();
    },

    async updateStudent(id, data) {
        const res = await fetchWithAuth(`${API_BASE}/students/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error('Failed to update student');
        return res.json();
    },

    async deleteStudent(id) {
        const res = await fetchWithAuth(`${API_BASE}/students/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete student');
        return res.json();
    },

    async getSchedule(group, date) {
        let url = `${API_BASE}/schedule?date=${encodeURIComponent(date)}`;
        if (group) {
            url += `&group=${encodeURIComponent(group)}`;
        }
        const res = await fetchWithAuth(url);
        if (!res.ok) throw new Error('Failed to fetch schedule');
        return res.json();
    },

    async getWeekSchedule(group, weekStart) {
        const res = await fetchWithAuth(`${API_BASE}/schedule/week?group=${encodeURIComponent(group)}&week_start=${weekStart}`);
        if (!res.ok) throw new Error('Failed to fetch week schedule');
        return res.json();
    },

    async getAttendance(lessonId) {
        const res = await fetchWithAuth(`${API_BASE}/attendance?lesson_id=${encodeURIComponent(lessonId)}`);
        if (!res.ok) throw new Error('Failed to fetch attendance');
        return res.json();
    },

    async setAttendance(lessonId, studentId, status) {
        const res = await fetchWithAuth(`${API_BASE}/attendance`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lesson_id: lessonId, student_id: studentId, status })
        });
        if (!res.ok) throw new Error('Failed to set attendance');
        return res.json();
    },

    async getUsers() {
        const res = await fetchWithAuth(`${API_BASE}/users`);
        if (!res.ok) throw new Error('Failed to fetch users');
        return res.json();
    },

    async createUser(userData) {
        const res = await fetchWithAuth(`${API_BASE}/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        if (!res.ok) throw new Error('Failed to create user');
        return res.json();
    },

    async updateUser(userId, userData) {
        const res = await fetchWithAuth(`${API_BASE}/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        if (!res.ok) throw new Error('Failed to update user');
        return res.json();
    },

    async deleteUser(userId) {
        const res = await fetchWithAuth(`${API_BASE}/users/${userId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete user');
        return res.json()
    },

    async downloadReport(groupCode, startDate, endDate, format) {
        const params = new URLSearchParams({
            group_code: groupCode,
            start_date: startDate,
            end_date: endDate,
            format: format
        });
        const url = `${API_BASE}/report?${params.toString()}`;
        const response = await fetchWithAuth(url, {
            method: 'GET',
            headers: {
                'Accept': format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Failed to generate report: ${errorText}`);
        }
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `report_${groupCode}_${startDate}_${endDate}.${format}`;
        if (contentDisposition) {
            const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (match && match[1]) {
                filename = match[1].replace(/['"]/g, '');
            }
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
    }
};