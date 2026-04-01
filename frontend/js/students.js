import { Utils } from './utils.js';

export class StudentsManager {
    constructor(app) {
        this.app = app;
    }

    async showModal() {
        const group = this.app.selectedGroup;
        if (!group) {
            this.app.showNotification('Сначала выберите группу', 'warning');
            return;
        }

        const students = this.app.students;

        const modalHtml = `
            <div class="modal-overlay" id="studentsModal">
                <div class="modal modal-lg">
                    <div class="modal-header">
                        <h2 class="modal-title">Управление студентами</h2>
                        <button class="modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="add-student">
                            <input type="text" id="newStudentName" placeholder="ФИО нового студента" class="form-control">
                            <select id="newStudentSubgroup" class="form-control" style="margin-top: 8px;">
                                <option value="0">Общая группа</option>
                                <option value="1">Первая подгруппа</option>
                                <option value="2">Вторая подгруппа</option>
                            </select>
                            <button id="addStudentBtn" class="btn btn-primary" style="margin-top: 8px;">Добавить</button>
                        </div>
                        <div class="export-buttons" style="margin-top: 16px;">
                            <button id="exportCsv" class="btn btn-sm btn-outline">Экспорт CSV</button>
                            <button id="exportTxt" class="btn btn-sm btn-outline">Экспорт TXT</button>
                        </div>
                        <div class="students-list" id="studentsListModal"></div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="closeStudentsBtn">Закрыть</button>
                    </div>
                </div>
            </div>
        `;

        const container = document.getElementById('modalsContainer');
        container.innerHTML = modalHtml;

        const modal = document.getElementById('studentsModal');
        const closeModal = () => modal.remove();

        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        document.getElementById('closeStudentsBtn').addEventListener('click', closeModal);

        const renderStudents = async () => {
            const currentStudents = this.app.students;
            const listDiv = document.getElementById('studentsListModal');
            if (!students.length) {
                listDiv.innerHTML = '<p class="empty-state">Студентов пока нет</p>';
                return;
            }
            listDiv.innerHTML = '';
            for (const student of currentStudents) {
                const row = document.createElement('div');
                row.className = 'student-row';
                const subgroupText = student.subgroup === 0 ? 'Общая' : (student.subgroup === 1 ? '1-я подгр.' : '2-я подгр.');
                row.innerHTML = `
                    <div class="student-info">
                        <strong>${Utils.escapeHtml(student.full_name)}</strong>
                        <div class="student-notes">${subgroupText}${student.notes ? ` • ${Utils.escapeHtml(student.notes)}` : ''}</div>
                    </div>
                    <div class="student-actions">
                        <button class="btn btn-sm btn-outline edit-student" data-id="${student.id}">✏️</button>
                        <button class="btn btn-sm btn-danger delete-student" data-id="${student.id}">🗑️</button>
                    </div>
                `;
                listDiv.appendChild(row);
            }

            listDiv.querySelectorAll('.edit-student').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const id = parseInt(btn.dataset.id);
                    const student = students.find(s => s.id === id);
                    const newName = prompt('Новое ФИО:', student.full_name);
                    if (newName && newName !== student.full_name) {
                        await this.app.api.updateStudent(id, { full_name: newName });
                        await this.app.refreshStudents();
                        renderStudents();
                        this.app.showNotification('Студент обновлён', 'success');
                    }
                    const newSubgroup = prompt('Номер подгруппы (0 - общая, 1 - первая, 2 - вторая):', student.subgroup);
                    if (newSubgroup !== null && parseInt(newSubgroup) !== student.subgroup) {
                        await this.app.api.updateStudent(id, { subgroup: parseInt(newSubgroup) });
                        await this.app.refreshStudents();
                        renderStudents();
                        this.app.showNotification('Подгруппа обновлена', 'success');
                    }
                });
            });

            listDiv.querySelectorAll('.delete-student').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const id = parseInt(btn.dataset.id);
                    if (confirm('Удалить студента?')) {
                        await this.app.api.deleteStudent(id);
                        await this.app.refreshStudents();
                        renderStudents();
                        this.app.showNotification('Студент удалён', 'success');
                    }
                });
            });
        };

        await renderStudents();

        // Добавление студента
        const addBtn = document.getElementById('addStudentBtn');
        const nameInput = document.getElementById('newStudentName');
        const subgroupSelect = document.getElementById('newStudentSubgroup');
        addBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const name = nameInput.value.trim();
            if (!name) {
                this.app.showNotification('Введите ФИО', 'warning');
                return;
            }
            const subgroup = parseInt(subgroupSelect.value);
            try {
                await this.app.api.addStudent(group, name, '', subgroup);
                // Обновляем глобальный список студентов
                await this.app.refreshStudents();

                // Перерисовываем список в модалке напрямую
                const updatedStudents = this.app.students;
                const listDiv = document.getElementById('studentsListModal');
                if (!listDiv) return;

                if (!updatedStudents.length) {
                    listDiv.innerHTML = '<p class="empty-state">Студентов пока нет</p>';
                } else {
                    listDiv.innerHTML = '';
                    for (const student of updatedStudents) {
                        const row = document.createElement('div');
                        row.className = 'student-row';
                        const subgroupText = student.subgroup === 0 ? 'Общая' : (student.subgroup === 1 ? '1-я подгр.' : '2-я подгр.');
                        row.innerHTML = `
                    <div class="student-info">
                        <strong>${Utils.escapeHtml(student.full_name)}</strong>
                        <div class="student-notes">${subgroupText}${student.notes ? ` • ${Utils.escapeHtml(student.notes)}` : ''}</div>
                    </div>
                    <div class="student-actions">
                        <button class="btn btn-sm btn-outline edit-student" data-id="${student.id}">✏️</button>
                        <button class="btn btn-sm btn-danger delete-student" data-id="${student.id}">🗑️</button>
                    </div>
                `;
                        listDiv.appendChild(row);
                    }
                    // Перевешиваем обработчики
                    listDiv.querySelectorAll('.edit-student').forEach(btn => {
                        btn.addEventListener('click', async () => {
                            const id = parseInt(btn.dataset.id);
                            const student = updatedStudents.find(s => s.id === id);
                            const newName = prompt('Новое ФИО:', student.full_name);
                            if (newName && newName !== student.full_name) {
                                await this.app.api.updateStudent(id, { full_name: newName });
                                await this.app.refreshStudents();
                                this.app.showNotification('Студент обновлён', 'success');
                            }
                            const newSubgroup = prompt('Номер подгруппы (0 - общая, 1 - первая, 2 - вторая):', student.subgroup);
                            if (newSubgroup !== null && parseInt(newSubgroup) !== student.subgroup) {
                                await this.app.api.updateStudent(id, { subgroup: parseInt(newSubgroup) });
                                await this.app.refreshStudents();
                                this.app.showNotification('Подгруппа обновлена', 'success');
                            }
                        });
                    });
                    listDiv.querySelectorAll('.delete-student').forEach(btn => {
                        btn.addEventListener('click', async () => {
                            const id = parseInt(btn.dataset.id);
                            if (confirm('Удалить студента?')) {
                                await this.app.api.deleteStudent(id);
                                await this.app.refreshStudents();
                                this.app.showNotification('Студент удалён', 'success');
                            }
                        });
                    });
                }

                nameInput.value = '';
                subgroupSelect.value = '0';
                this.app.showNotification('Студент добавлен', 'success');
            } catch (err) {
                console.error('Add student error:', err);
                this.app.showNotification('Ошибка при добавлении студента', 'error');
            }
        });

        // Экспорт
        document.getElementById('exportCsv').addEventListener('click', () => this.exportStudents('csv'));
        document.getElementById('exportTxt').addEventListener('click', () => this.exportStudents('txt'));
    }

    async exportStudents(format) {
        const students = this.app.students;
        if (!students.length) {
            this.app.showNotification('Нет студентов для экспорта', 'warning');
            return;
        }
        if (format === 'csv') {
            const rows = [['ФИО', 'Подгруппа', 'Примечания']];
            students.forEach(s => {
                let subgroupText = '';
                if (s.subgroup === 0) subgroupText = 'Общая';
                else if (s.subgroup === 1) subgroupText = '1-я подгр.';
                else if (s.subgroup === 2) subgroupText = '2-я подгр.';
                rows.push([s.full_name, subgroupText, s.notes || '']);
            });
            const csvContent = rows.map(row => row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\n');
            const blob = new Blob(["\uFEFF" + csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.href = url;
            link.setAttribute('download', `students_${this.app.selectedGroup}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        } else if (format === 'txt') {
            const lines = students.map(s => `${s.full_name} (${s.subgroup === 1 ? '1 подгр.' : s.subgroup === 2 ? '2 подгр.' : 'общая'})`);
            const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.href = url;
            link.setAttribute('download', `students_${this.app.selectedGroup}.txt`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }
    }
}