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
            const listDiv = document.getElementById('studentsListModal');
            if (!students.length) {
                listDiv.innerHTML = '<p class="empty-state">Студентов пока нет</p>';
                return;
            }
            listDiv.innerHTML = '';
            for (const student of students) {
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

            // Обработчики
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
                    // NEW: возможность изменить подгруппу
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
        addBtn.addEventListener('click', async () => {
            const name = nameInput.value.trim();
            if (!name) {
                this.app.showNotification('Введите ФИО', 'warning');
                return;
            }
            const subgroup = parseInt(subgroupSelect.value);
            await this.app.api.addStudent(group, name, '', subgroup);
            await this.app.refreshStudents();
            nameInput.value = '';
            subgroupSelect.value = '0';
            renderStudents();
            this.app.showNotification('Студент добавлен', 'success');
        });
    }
}