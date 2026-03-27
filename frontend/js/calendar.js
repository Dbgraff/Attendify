import { Utils } from './utils.js';

export class CalendarManager {
    constructor(app) {
        this.app = app;
        this.selectedDate = new Date();
        this.flatpickr = null;
    }

    init() {
        const input = document.getElementById('datePicker');
        if (!input) return;

        this.flatpickr = flatpickr(input, {
            locale: 'ru',
            dateFormat: 'd.m.Y',
            defaultDate: this.selectedDate,
            onChange: async (dates) => {
                if (dates.length) {
                    this.selectedDate = dates[0];
                    this.updateDateText();
                    try {
                        await this.app.refreshSchedule();
                    } catch (err) {
                        console.error('Error refreshing schedule on date change:', err);
                    }
                }
            }
        });

        this.updateDateText();

        const prevBtn = document.getElementById('prevDayBtn');
        const todayBtn = document.getElementById('todayBtn');
        const nextBtn = document.getElementById('nextDayBtn');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                const newDate = new Date(this.selectedDate);
                newDate.setDate(newDate.getDate() - 1);
                this.setSelectedDate(newDate);
            });
        }
        if (todayBtn) {
            todayBtn.addEventListener('click', () => {
                this.setSelectedDate(new Date());
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                const newDate = new Date(this.selectedDate);
                newDate.setDate(newDate.getDate() + 1);
                this.setSelectedDate(newDate);
            });
        }
    }

    updateDateText() {
        const dateText = document.getElementById('selectedDateText');
        if (!dateText) return;

        const today = new Date();
        if (this.selectedDate.toDateString() === today.toDateString()) {
            dateText.textContent = 'Сегодня';
        } else {
            dateText.textContent = Utils.formatDate(this.selectedDate);
        }
    }

    getSelectedDate() {
        return new Date(this.selectedDate);
    }

    setSelectedDate(date) {
        this.selectedDate = new Date(date);
        if (this.flatpickr) {
            this.flatpickr.setDate(this.selectedDate);
        }
        this.updateDateText();
        if (this.app && typeof this.app.refreshSchedule === 'function') {
            this.app.refreshSchedule().catch(err => console.error('Error refreshing schedule:', err));
        }
    }
}