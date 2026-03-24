const API_BASE = 'http://localhost:5000'; // замените на ваш адрес

export const api = {
    // Группы
    async getGroups() {
        const res = await fetch(`${API_BASE}/groups`);
        if (!res.ok) throw new Error('Failed to fetch groups');
        return res.json();
    },

    // Студенты
    async getStudents(groupCode) {
        const res = await fetch(`${API_BASE}/students?group=${encodeURIComponent(groupCode)}`);
        if (!res.ok) throw new Error('Failed to fetch students');
        return res.json();
    },
async addStudent(groupCode, fullName, notes = '', subgroup = 0) {
        const res = await fetch(`${API_BASE}/students`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group: groupCode, full_name: fullName, notes, subgroup })
        });
        if (!res.ok) throw new Error('Failed to add student');
        return res.json();
    },
    async updateStudent(id, data) {
        const res = await fetch(`${API_BASE}/students/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error('Failed to update student');
        return res.json();
    },
    async deleteStudent(id) {
        const res = await fetch(`${API_BASE}/students/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete student');
        return res.json();
    },

    // Расписание
    async getSchedule(group, date) {
        const res = await fetch(`${API_BASE}/schedule?group=${encodeURIComponent(group)}&date=${date}`);
        if (!res.ok) throw new Error('Failed to fetch schedule');
        return res.json();
    },
    async getWeekSchedule(group, weekStart) {
        const res = await fetch(`${API_BASE}/schedule/week?group=${encodeURIComponent(group)}&week_start=${weekStart}`);
        if (!res.ok) throw new Error('Failed to fetch week schedule');
        return res.json();
    },

    // Посещаемость
    async getAttendance(lessonId) {
        const res = await fetch(`${API_BASE}/attendance?lesson_id=${encodeURIComponent(lessonId)}`);
        if (!res.ok) throw new Error('Failed to fetch attendance');
        return res.json();
    },
    async setAttendance(lessonId, studentId, status) {
        const res = await fetch(`${API_BASE}/attendance`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lesson_id: lessonId, student_id: studentId, status })
        });
        if (!res.ok) throw new Error('Failed to set attendance');
        return res.json();
    }
};