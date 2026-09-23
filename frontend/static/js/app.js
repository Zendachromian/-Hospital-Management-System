const { createApp } = Vue;

const API_URL = 'http://localhost:5000/api';

createApp({
    data() {
        return {
            currentUser: null,
            accessToken: localStorage.getItem('access_token'),
            isLogin: true,
            currentPage: 'dashboard',
            errorMessage: '',
            successMessage: '',
            
            authForm: {
                username: '',
                password: '',
                email: '',
                full_name: '',
                phone: '',
                date_of_birth: '',
                gender: ''
            },
            
            profileForm: {
                full_name: '',
                email: '',
                phone: '',
                date_of_birth: '',
                gender: '',
                address: '',
                blood_group: '',
                emergency_contact: ''
            },
            
            dashboardStats: {},
            doctorStats: {},
            patientStats: {},
            charts: {},
            
            appointments: [],
            doctors: [],
            patients: [],
            departments: [],
            allDepartments: [],
            treatmentHistory: [],
            doctorsAvailability: [],
            
            notifications: [],
            unreadNotificationCount: 0,
            
            doctorSearchQuery: '',
            patientSearchQuery: '',
            doctorFinderSearchQuery: '',
            
            showInactiveDoctors: true,
            showInactivePatients: true,
            
            showAddDoctorModal: false,
            showBookingModal: false,
            showTreatmentModal: false,
            showDoctorsModal: false,
            showDoctorProfileModal: false,
            autoSeedTried: false,
            showEditAppointmentModal: false,
            showPatientHistoryModal: false,
            showEditTreatmentModal: false,
            showPaymentModal: false,
            
            doctorForm: {},
            bookingForm: {},
            treatmentForm: {},
            editAppointmentForm: {},
            editTreatmentForm: {},
            paymentForm: {
                card_holder_name: '',
                card_number: '',
                expiry: '',
                cvv: ''
            },
            
            pendingPayments: [],
            paymentHistory: [],
            selectedPaymentApt: null,
            
            // Calendar for appointment booking
            calendarYear: new Date().getFullYear(),
            calendarMonth: new Date().toLocaleString('default', { month: 'long', year: 'numeric' }),
            calendarDates: [],
            dateAvailability: {},
            availabilityCache: {}, // Cache: doctorId_month -> availability data
            
            // Calendar for editing appointments
            editCalendarYear: new Date().getFullYear(),
            editCalendarMonth: new Date().toLocaleString('default', { month: 'long', year: 'numeric' }),
            editCalendarDates: [],
            editDateAvailability: {},
            editAvailabilityCache: {}, // Cache: doctorId_month -> availability data
            editAvailableSlots: [],
            
            editingDoctor: null,
            editingAppointment: null,
            selectedDoctor: {},
            selectedDepartment: {},
            departmentDoctors: [],
            currentAppointment: null,
            selectedPatient: null,
            patientHistory: [],
            myPatients: [],
            availabilityDays: [],
            notifications: [],
            showNotificationModal: false,
            
            // Debug info
            debugInfo: '',
            isLoading: false,
            isLoggingIn: false,
            isRegistering: false,
            loadingSlotsDate: null  // Track which date is loading
        };
    },
    
    async mounted() {
        // Restore current page from localStorage
        const savedPage = localStorage.getItem('currentPage');
        if (savedPage && this.accessToken) {
            this.currentPage = savedPage;
        }
        
        if (this.accessToken) {
            await this.loadUser();
        }
    },
    
    methods: {
        async apiCall(method, endpoint, data = null) {
            try {
                const config = {
                    method,
                    url: `${API_URL}${endpoint}`,
                    headers: {}
                };
                
                if (this.accessToken) {
                    config.headers['Authorization'] = `Bearer ${this.accessToken}`;
                }
                
                if (data) {
                    config.headers['Content-Type'] = 'application/json';
                    config.data = data;
                }
                
                const response = await axios(config);
                return response.data;
            } catch (error) {
                console.error('API Error:', error);
                if (error.response && error.response.status === 401) {
                    this.logout();
                }
                throw error;
            }
        },
        
        async login() {
            try {
                this.errorMessage = '';
                this.isLoggingIn = true;
                const response = await this.apiCall('POST', '/auth/login', {
                    username: this.authForm.username,
                    password: this.authForm.password
                });
                
                this.accessToken = response.access_token;
                localStorage.setItem('access_token', this.accessToken);
                this.currentUser = response.user;
                await this.checkNotifications();
                this.changePage('dashboard');
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Login failed. Please check your credentials.';
            } finally {
                this.isLoggingIn = false;
            }
        },
        
        async register() {
            try {
                this.errorMessage = '';
                this.successMessage = '';
                this.isRegistering = true;
                await this.apiCall('POST', '/auth/register', this.authForm);
                this.successMessage = 'Registration successful! Please login with your credentials.';
                this.isLogin = true;
                this.authForm = { username: '', password: '', email: '', full_name: '', phone: '', date_of_birth: '', gender: '' };
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Registration failed. Please try again.';
            } finally {
                this.isRegistering = false;
            }
        },
        
        async loadUser() {
            try {
                const response = await this.apiCall('GET', '/auth/profile');
                this.currentUser = response.user;
                await this.checkNotifications();
                
                // Only change page if no saved page exists or saved page is login/register
                const savedPage = localStorage.getItem('currentPage');
                if (!savedPage || savedPage === 'login' || savedPage === 'register') {
                    this.changePage('dashboard');
                } else {
                    // Restore saved page and load its data
                    this.changePage(savedPage);
                }
            } catch (error) {
                this.logout();
            }
        },
        
        async checkNotifications() {
            try {
                const response = await this.apiCall('GET', '/auth/notifications');
                this.notifications = response.notifications || [];
                this.unreadNotificationCount = this.notifications.length;
                if (this.notifications.length > 0) {
                    this.showNotificationModal = true;
                }
            } catch (error) {
                console.error('Error loading notifications:', error);
            }
        },
        
        async markNotificationRead(notificationId) {
            try {
                await this.apiCall('PUT', `/auth/notifications/${notificationId}`);
                this.notifications = this.notifications.filter(n => n.id !== notificationId);
                this.unreadNotificationCount = this.notifications.length;
                if (this.notifications.length === 0) {
                    this.showNotificationModal = false;
                }
            } catch (error) {
                console.error('Error marking notification as read:', error);
            }
        },
        
        async markAllNotificationsRead() {
            try {
                await this.apiCall('POST', '/auth/notifications/mark-all-read');
                this.notifications = [];
                this.unreadNotificationCount = 0;
                this.showNotificationModal = false;
            } catch (error) {
                console.error('Error marking all notifications as read:', error);
            }
        },
        
        logout() {
            this.currentUser = null;
            this.accessToken = null;
            localStorage.removeItem('access_token');
            localStorage.removeItem('currentPage');
            this.authForm = { username: '', password: '', email: '', full_name: '', phone: '', date_of_birth: '', gender: '' };
        },
        
        showAlert(message, type = 'info') {
            if (type === 'success') {
                this.successMessage = message;
                this.errorMessage = '';
            } else if (type === 'danger' || type === 'error') {
                this.errorMessage = message;
                this.successMessage = '';
            } else {
                this.successMessage = message;
                this.errorMessage = '';
            }
            
            // Auto-dismiss after 4 seconds
            setTimeout(() => {
                this.successMessage = '';
                this.errorMessage = '';
            }, 4000);
        },
        
        toggleAuthMode() {
            this.isLogin = !this.isLogin;
            this.errorMessage = '';
            this.successMessage = '';
            this.authForm = { username: '', password: '', email: '', full_name: '', phone: '', date_of_birth: '', gender: '' };
        },
        
        async changePage(page) {
            this.currentPage = page;
            localStorage.setItem('currentPage', page);
            this.errorMessage = '';
            this.successMessage = '';
            
            if (page === 'dashboard') {
                if (this.currentUser.role === 'admin') {
                    await this.loadAdminDashboard();
                } else if (this.currentUser.role === 'doctor') {
                    await this.loadDoctorDashboard();
                } else if (this.currentUser.role === 'patient') {
                    await this.loadPatientDashboard();
                }
            } else if (page === 'doctors') {
                await this.loadDoctors();
                await this.loadDepartments();
            } else if (page === 'patients') {
                await this.loadPatients();
            } else if (page === 'departments') {
                await this.loadDepartments();
            } else if (page === 'appointments') {
                await this.loadAppointments();
            } else if (page === 'history') {
                await this.loadTreatmentHistory();
            } else if (page === 'profile') {
                await this.loadProfile();
            } else if (page === 'payments') {
                await this.loadPayments();
            } else if (page === 'my-patients') {
                await this.loadMyPatients();
            } else if (page === 'availability') {
                await this.loadAvailability();
            }
        },
        
        async loadAdminDashboard() {
            try {
                const stats = await this.apiCall('GET', '/admin/dashboard');
                this.dashboardStats = stats;
                const appts = await this.apiCall('GET', '/admin/appointments');
                this.appointments = appts.appointments;
                
                // Wait for Vue to render the canvas elements
                await this.$nextTick();
                this.renderCharts();
            } catch (error) {
                console.error('Error loading admin dashboard:', error);
            }
        },
        
        renderCharts() {
            // Destroy existing charts if they exist
            if (this.charts) {
                Object.values(this.charts).forEach(chart => {
                    if (chart) chart.destroy();
                });
            }
            this.charts = {};
            
            // Appointment Status Chart (Pie)
            const statusCtx = document.getElementById('appointmentStatusChart');
            if (statusCtx && this.dashboardStats.appointment_status) {
                const statusData = this.dashboardStats.appointment_status;
                this.charts.status = new Chart(statusCtx, {
                    type: 'pie',
                    data: {
                        labels: Object.keys(statusData),
                        datasets: [{
                            data: Object.values(statusData),
                            backgroundColor: [
                                'rgba(54, 162, 235, 0.8)',  // Booked - Blue
                                'rgba(75, 192, 192, 0.8)',  // Completed - Green
                                'rgba(255, 99, 132, 0.8)',  // Cancelled - Red
                            ],
                            borderColor: [
                                'rgba(54, 162, 235, 1)',
                                'rgba(75, 192, 192, 1)',
                                'rgba(255, 99, 132, 1)',
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
            }
            
            // Department Chart (Bar)
            const deptCtx = document.getElementById('departmentChart');
            if (deptCtx && this.dashboardStats.appointments_by_department) {
                const deptData = this.dashboardStats.appointments_by_department;
                this.charts.department = new Chart(deptCtx, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(deptData),
                        datasets: [{
                            label: 'Appointments',
                            data: Object.values(deptData),
                            backgroundColor: 'rgba(75, 192, 192, 0.6)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            }
            
            // Appointment Trend Chart (Line)
            const trendCtx = document.getElementById('appointmentTrendChart');
            if (trendCtx && this.dashboardStats.appointments_trend) {
                const trendData = this.dashboardStats.appointments_trend;
                this.charts.trend = new Chart(trendCtx, {
                    type: 'line',
                    data: {
                        labels: trendData.map(d => new Date(d.date).toLocaleDateString('en-US', {month: 'short', day: 'numeric'})),
                        datasets: [{
                            label: 'Appointments',
                            data: trendData.map(d => d.count),
                            backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4,
                            pointRadius: 5,
                            pointHoverRadius: 7
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            }
            
            // Gender Distribution Chart (Doughnut)
            const genderCtx = document.getElementById('genderChart');
            if (genderCtx && this.dashboardStats.gender_distribution) {
                const genderData = this.dashboardStats.gender_distribution;
                this.charts.gender = new Chart(genderCtx, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(genderData),
                        datasets: [{
                            data: Object.values(genderData),
                            backgroundColor: [
                                'rgba(54, 162, 235, 0.8)',  // Male - Blue
                                'rgba(255, 99, 132, 0.8)',  // Female - Pink
                                'rgba(255, 206, 86, 0.8)',  // Other - Yellow
                            ],
                            borderColor: [
                                'rgba(54, 162, 235, 1)',
                                'rgba(255, 99, 132, 1)',
                                'rgba(255, 206, 86, 1)',
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
            }

            // Top Doctors by Appointments (Horizontal Bar)
            const topDoctorsCtx = document.getElementById('topDoctorsChart');
            if (topDoctorsCtx && this.dashboardStats.top_doctors && this.dashboardStats.top_doctors.length > 0) {
                const topDocs = this.dashboardStats.top_doctors;
                this.charts.topDoctors = new Chart(topDoctorsCtx, {
                    type: 'bar',
                    data: {
                        labels: topDocs.map(d => d.name),
                        datasets: [{
                            label: 'Appointments',
                            data: topDocs.map(d => d.appointment_count),
                            backgroundColor: [
                                'rgba(255, 107, 107, 0.8)',
                                'rgba(255, 153, 102, 0.8)',
                                'rgba(255, 195, 113, 0.8)',
                                'rgba(120, 180, 255, 0.8)',
                                'rgba(100, 200, 200, 0.8)',
                            ],
                            borderColor: [
                                'rgba(255, 107, 107, 1)',
                                'rgba(255, 153, 102, 1)',
                                'rgba(255, 195, 113, 1)',
                                'rgba(120, 180, 255, 1)',
                                'rgba(100, 200, 200, 1)',
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            x: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            }

            // Appointment Completion Rate (Horizontal Bar)
            const completionCtx = document.getElementById('completionRateChart');
            if (completionCtx && this.dashboardStats.appointment_status) {
                const statusData = this.dashboardStats.appointment_status;
                const total = Object.values(statusData).reduce((a, b) => a + b, 0);
                const rates = {
                    'Completed': ((statusData.Completed || 0) / total * 100).toFixed(1),
                    'Booked': ((statusData.Booked || 0) / total * 100).toFixed(1),
                    'Cancelled': ((statusData.Cancelled || 0) / total * 100).toFixed(1),
                };
                this.charts.completion = new Chart(completionCtx, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(rates),
                        datasets: [{
                            label: 'Percentage (%)',
                            data: Object.values(rates),
                            backgroundColor: [
                                'rgba(75, 192, 75, 0.8)',
                                'rgba(54, 162, 235, 0.8)',
                                'rgba(255, 99, 132, 0.8)',
                            ],
                            borderColor: [
                                'rgba(75, 192, 75, 1)',
                                'rgba(54, 162, 235, 1)',
                                'rgba(255, 99, 132, 1)',
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            x: {
                                max: 100,
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            }

            // Peak Appointment Times (Bar)
            const peakTimesCtx = document.getElementById('peakTimesChart');
            if (peakTimesCtx && this.dashboardStats.peak_appointment_times && this.dashboardStats.peak_appointment_times.length > 0) {
                const peakTimes = this.dashboardStats.peak_appointment_times;
                this.charts.peakTimes = new Chart(peakTimesCtx, {
                    type: 'bar',
                    data: {
                        labels: peakTimes.map(t => t.time_slot),
                        datasets: [{
                            label: 'Number of Appointments',
                            data: peakTimes.map(t => t.count),
                            backgroundColor: 'rgba(153, 102, 255, 0.6)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            }

            // Department Load (Busiest Departments)
            const deptLoadCtx = document.getElementById('departmentLoadChart');
            if (deptLoadCtx && this.dashboardStats.appointments_by_department) {
                const deptData = this.dashboardStats.appointments_by_department;
                const sorted = Object.entries(deptData)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 6);
                
                if (sorted.length > 0) {
                    this.charts.deptLoad = new Chart(deptLoadCtx, {
                    type: 'bar',
                    data: {
                        labels: sorted.map(d => d[0]),
                        datasets: [{
                            label: 'Appointments',
                            data: sorted.map(d => d[1]),
                            backgroundColor: [
                                'rgba(255, 159, 64, 0.8)',
                                'rgba(255, 99, 132, 0.8)',
                                'rgba(54, 162, 235, 0.8)',
                                'rgba(75, 192, 192, 0.8)',
                                'rgba(201, 203, 207, 0.8)',
                                'rgba(255, 206, 86, 0.8)',
                            ],
                            borderColor: [
                                'rgba(255, 159, 64, 1)',
                                'rgba(255, 99, 132, 1)',
                                'rgba(54, 162, 235, 1)',
                                'rgba(75, 192, 192, 1)',
                                'rgba(201, 203, 207, 1)',
                                'rgba(255, 206, 86, 1)',
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                    });
                }
            }
        },
        
        async loadDoctorDashboard() {
            try {
                const response = await this.apiCall('GET', '/doctor/dashboard');
                this.doctorStats = response;
            } catch (error) {
                console.error('Error loading doctor dashboard:', error);
            }
        },
        
        async loadPatientDashboard() {
            try {
                const response = await this.apiCall('GET', '/patient/dashboard');
                this.patientStats = response;
                this.departments = response.departments;
                await this.loadDoctorsAvailability();
            } catch (error) {
                console.error('Error loading patient dashboard:', error);
            }
        },
        
        async loadDoctorsAvailability() {
            try {
                const response = await this.apiCall('GET', '/patient/doctors/availability');
                this.doctorsAvailability = response.doctors;
            } catch (error) {
                console.error('Error loading doctors availability:', error);
            }
        },
        
        async loadDoctors() {
            try {
                let url = '/admin/doctors';
                const params = [];
                if (this.doctorSearchQuery) {
                    params.push(`search=${encodeURIComponent(this.doctorSearchQuery)}`);
                }
                if (this.showInactiveDoctors) {
                    params.push('show_inactive=true');
                }
                if (params.length > 0) {
                    url += '?' + params.join('&');
                }
                console.log('Loading doctors from:', url);
                const response = await this.apiCall('GET', url);
                console.log('Received doctors:', response.doctors);
                // Ensure Vue detects the change by creating a new array reference
                this.doctors = [...response.doctors];
            } catch (error) {
                console.error('Error loading doctors:', error);
            }
        },
        
        toggleInactiveDoctors() {
            this.showInactiveDoctors = !this.showInactiveDoctors;
            this.loadDoctors();
        },
        
        async searchDoctors() {
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => {
                this.loadDoctors();
            }, 300);
        },
        
        async loadPatients() {
            try {
                let url = '/admin/patients';
                const params = [];
                if (this.patientSearchQuery) {
                    params.push(`search=${encodeURIComponent(this.patientSearchQuery)}`);
                }
                if (this.showInactivePatients) {
                    params.push('show_inactive=true');
                }
                if (params.length > 0) {
                    url += '?' + params.join('&');
                }
                console.log('Loading patients from:', url);
                const response = await this.apiCall('GET', url);
                console.log('Received patients:', response.patients);
                // Ensure Vue detects the change by creating a new array reference
                this.patients = [...response.patients];
            } catch (error) {
                console.error('Error loading patients:', error);
            }
        },
        
        async searchPatients() {
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => {
                this.loadPatients();
            }, 300);
        },
        
        toggleInactivePatients() {
            this.showInactivePatients = !this.showInactivePatients;
            this.loadPatients();
        },
        
        async loadDepartments() {
            try {
                this.isLoading = true;
                let endpoint = this.currentUser.role === 'admin' ? '/admin/departments' : '/patient/departments';
                console.log('Loading departments from:', endpoint);
                
                const response = await this.apiCall('GET', endpoint);
                
                // Debug logging
                console.log('Departments API response:', response);
                
                if (response.departments && Array.isArray(response.departments)) {
                    this.departments = response.departments;
                    this.allDepartments = response.departments;
                    console.log(`Successfully loaded ${this.allDepartments.length} departments`);
                    
                    // Auto-seed for admin if none exist (one-time)
                    if (this.currentUser.role === 'admin' && this.allDepartments.length === 0 && !this.autoSeedTried) {
                        try {
                            console.log('No departments found. Auto-seeding default departments...');
                            this.autoSeedTried = true;
                            await this.apiCall('POST', '/admin/departments/seed');
                            // Reload after seeding
                            const resp2 = await this.apiCall('GET', endpoint);
                            this.departments = resp2.departments || [];
                            this.allDepartments = resp2.departments || [];
                        } catch (seedErr) {
                            console.error('Auto-seed failed:', seedErr);
                        }
                    }

                    // Update debug info
                    this.debugInfo = `Loaded ${this.allDepartments.length} departments: ` + 
                        this.allDepartments.map(dept => dept.name).join(', ');
                } else {
                    console.error('Unexpected departments response format:', response);
                    this.departments = [];
                    this.allDepartments = [];
                    this.debugInfo = 'No departments found or invalid response format';
                }
            } catch (error) {
                console.error('Error loading departments:', error);
                this.departments = [];
                this.allDepartments = [];
                this.debugInfo = `Error loading departments: ${error.response?.data?.error || error.message}`;
            } finally {
                this.isLoading = false;
            }
        },
        
        async loadAppointments() {
            try {
                let endpoint;
                if (this.currentUser.role === 'patient') {
                    endpoint = '/patient/appointments';
                } else if (this.currentUser.role === 'doctor') {
                    endpoint = '/doctor/appointments';
                } else if (this.currentUser.role === 'admin') {
                    endpoint = '/admin/appointments';
                }
                
                const response = await this.apiCall('GET', endpoint);
                this.appointments = response.appointments;
            } catch (error) {
                console.error('Error loading appointments:', error);
            }
        },
        
        async loadTreatmentHistory() {
            try {
                const response = await this.apiCall('GET', '/patient/history');
                this.treatmentHistory = response.history;
            } catch (error) {
                console.error('Error loading treatment history:', error);
            }
        },
        
        async loadPatientTreatmentHistory() {
            try {
                const response = await this.apiCall('GET', '/patient/history');
                this.patientHistory = response.history || [];
            } catch (error) {
                console.error('Error loading patient treatment history:', error);
                this.patientHistory = [];
            }
        },

        // Luhn Algorithm for credit card validation
        validateLuhn(cardNumber) {
            let sum = 0;
            let isEven = false;
            
            for (let i = cardNumber.length - 1; i >= 0; i--) {
                let digit = parseInt(cardNumber.charAt(i), 10);
                
                if (isEven) {
                    digit *= 2;
                    if (digit > 9) {
                        digit -= 9;
                    }
                }
                
                sum += digit;
                isEven = !isEven;
            }
            
            return (sum % 10) === 0;
        },

        async loadPayments() {
            try {
                // Load pending payments
                const pendingResp = await this.apiCall('GET', '/patient/completed-appointments');
                this.pendingPayments = pendingResp.appointments.filter(apt => !apt.is_paid) || [];
                
                // Load payment history
                const historyResp = await this.apiCall('GET', '/patient/payment-history');
                this.paymentHistory = historyResp.payments || [];
            } catch (error) {
                console.error('Error loading payments:', error);
                this.pendingPayments = [];
                this.paymentHistory = [];
            }
        },

        openPaymentModal(appointment) {
            this.selectedPaymentApt = appointment;
            this.paymentForm = {
                card_holder_name: '',
                card_number: '',
                expiry: '',
                cvv: ''
            };
            this.showPaymentModal = true;
        },

        async submitPayment() {
            if (!this.selectedPaymentApt) return;
            
            // Validate form fields are not empty
            if (!this.paymentForm.card_holder_name || !this.paymentForm.card_number || 
                !this.paymentForm.expiry || !this.paymentForm.cvv) {
                this.errorMessage = 'Please fill in all payment details';
                return;
            }
            
            // CARDHOLDER NAME VALIDATION
            const trimmedName = this.paymentForm.card_holder_name.trim();
            if (trimmedName.length < 2) {
                this.errorMessage = 'Cardholder name must be at least 2 characters';
                return;
            }
            if (trimmedName.length > 50) {
                this.errorMessage = 'Cardholder name must not exceed 50 characters';
                return;
            }
            const nameRegex = /^[A-Za-z\s]{2,50}$/;
            if (!nameRegex.test(trimmedName)) {
                this.errorMessage = 'Cardholder name must contain only letters and spaces';
                return;
            }
            
            // CARD NUMBER VALIDATION
            const cardNumber = this.paymentForm.card_number.replace(/\s/g, '');
            
            // Check if exactly 16 digits
            if (!/^[0-9]{16}$/.test(cardNumber)) {
                this.errorMessage = 'Card number must be exactly 16 digits';
                return;
            }
            
            // Check if numeric (no non-digit characters)
            if (isNaN(parseInt(cardNumber))) {
                this.errorMessage = 'Card number must contain only numeric digits';
                return;
            }
            
            // Validate using Luhn Algorithm (catches most invalid card numbers)
            if (!this.validateLuhn(cardNumber)) {
                this.errorMessage = 'Card number is invalid (failed validation check)';
                return;
            }
            
            // Check for obviously fake test cards (all same digits)
            if (/^(\d)\1{15}$/.test(cardNumber)) {
                this.errorMessage = 'Card number cannot contain all identical digits';
                return;
            }
            
            // EXPIRY DATE VALIDATION
            const expiryRegex = /^(0[1-9]|1[0-2])\/[0-9]{2}$/;
            if (!expiryRegex.test(this.paymentForm.expiry)) {
                this.errorMessage = 'Expiry date must be in MM/YY format with valid month (01-12)';
                return;
            }
            
            const [month, year] = this.paymentForm.expiry.split('/');
            const currentDate = new Date();
            const currentYear = currentDate.getFullYear() % 100;
            const currentMonth = currentDate.getMonth() + 1;
            
            const expiryYear = parseInt(year);
            const expiryMonth = parseInt(month);
            
            // Check if card is expired
            if (expiryYear < currentYear || (expiryYear === currentYear && expiryMonth < currentMonth)) {
                this.errorMessage = 'Card has expired. Please use a valid card.';
                return;
            }
            
            // Check if expiry is not too far in future (max 20 years)
            const maxYear = currentYear + 20;
            if (expiryYear > maxYear) {
                this.errorMessage = 'Expiry date is too far in the future (max 20 years)';
                return;
            }
            
            // CVV VALIDATION
            if (!/^[0-9]{3}$/.test(this.paymentForm.cvv)) {
                this.errorMessage = 'CVV must be exactly 3 numeric digits';
                return;
            }
            
            if (isNaN(parseInt(this.paymentForm.cvv))) {
                this.errorMessage = 'CVV must contain only numeric digits';
                return;
            }
            
            // Check if CVV is not all zeros or same digits
            if (/^(0){3}$/.test(this.paymentForm.cvv) || /^(\d)\1{2}$/.test(this.paymentForm.cvv)) {
                this.errorMessage = 'CVV appears invalid';
                return;
            }
            
            // AMOUNT VALIDATION
            if (!this.selectedPaymentApt.consultation_fee || this.selectedPaymentApt.consultation_fee <= 0) {
                this.errorMessage = 'Invalid payment amount';
                return;
            }
            
            if (this.selectedPaymentApt.consultation_fee > 999999) {
                this.errorMessage = 'Payment amount exceeds maximum limit';
                return;
            }
            
            // Clear error messages
            this.errorMessage = null;
            
            try {
                this.isLoading = true;
                const response = await this.apiCall('POST', '/patient/process-payment', {
                    appointment_id: this.selectedPaymentApt.id,
                    card_holder_name: this.paymentForm.card_holder_name,
                    card_number: this.paymentForm.card_number,
                    amount: this.selectedPaymentApt.consultation_fee
                });
                
                this.successMessage = `Payment successful! Transaction ID: ${response.transaction_id}`;
                this.showPaymentModal = false;
                
                // Reload payments
                await this.loadPayments();
                
                this.isLoading = false;
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Payment failed';
                this.isLoading = false;
            }
        },
        
        async testDepartments() {
            await this.loadDepartments();
            console.log('All departments:', this.allDepartments);
            alert(`Loaded ${this.allDepartments.length} departments. Check console for details.`);
        },
        
        editDoctor(doctor) {
            this.editingDoctor = doctor;
            this.doctorForm = { 
                ...doctor,
                gender: doctor.gender || ''
            };
            this.showAddDoctorModal = true;
        },
        
        async saveDoctor() {
            try {
                if (this.editingDoctor) {
                    await this.apiCall('PUT', `/admin/doctors/${this.editingDoctor.id}`, this.doctorForm);
                    alert('Doctor updated successfully');
                } else {
                    await this.apiCall('POST', '/admin/doctors', this.doctorForm);
                    alert('Doctor added successfully');
                }
                this.closeModal();
                await this.loadDoctors();
            } catch (error) {
                alert(error.response?.data?.error || 'Failed to save doctor');
            }
        },
        
        async deleteDoctor(doctorId) {
            if (confirm('Are you sure you want to deactivate this doctor?')) {
                try {
                    await this.apiCall('DELETE', `/admin/doctors/${doctorId}`);
                    this.showAlert('Doctor deactivated successfully', 'success');
                    await this.loadDoctors();
                } catch (error) {
                    this.showAlert('Failed to deactivate doctor', 'danger');
                }
            }
        },
        
        async reactivateDoctor(doctorId) {
            if (confirm('Are you sure you want to reactivate this doctor?')) {
                try {
                    const response = await this.apiCall('POST', `/admin/doctors/${doctorId}/reactivate`);
                    console.log('Reactivation response:', response);
                    this.showAlert('Doctor reactivated successfully', 'success');
                    // Force reload doctors list
                    await this.loadDoctors();
                    console.log('Doctors reloaded:', this.doctors.length);
                } catch (error) {
                    console.error('Reactivation error:', error);
                    this.showAlert('Failed to reactivate doctor: ' + (error.response?.data?.error || error.message), 'danger');
                }
            }
        },
        
        async deletePatient(patientId) {
            if (confirm('Are you sure you want to deactivate this patient?')) {
                try {
                    await this.apiCall('DELETE', `/admin/patients/${patientId}`);
                    this.showAlert('Patient deactivated successfully', 'success');
                    await this.loadPatients();
                } catch (error) {
                    this.showAlert('Failed to deactivate patient', 'danger');
                }
            }
        },
        
        async reactivatePatient(patientId) {
            if (confirm('Are you sure you want to reactivate this patient?')) {
                try {
                    const response = await this.apiCall('POST', `/admin/patients/${patientId}/reactivate`);
                    console.log('Reactivation response:', response);
                    this.showAlert('Patient reactivated successfully', 'success');
                    // Force reload patients list
                    await this.loadPatients();
                    console.log('Patients reloaded:', this.patients.length);
                } catch (error) {
                    console.error('Reactivation error:', error);
                    this.showAlert('Failed to reactivate patient: ' + (error.response?.data?.error || error.message), 'danger');
                }
            }
        },
        
        async viewDepartmentDoctors(dept) {
            try {
                this.selectedDepartment = dept;
                await this.loadDepartmentDoctors(dept.id);
                this.showDoctorsModal = true;
            } catch (error) {
                console.error('Error loading department doctors:', error);
            }
        },
        
        async loadDepartmentDoctors(departmentId = null) {
            try {
                let url = '/patient/doctors';
                const params = [];
                
                if (departmentId) {
                    params.push(`department_id=${departmentId}`);
                }
                if (this.doctorFinderSearchQuery) {
                    params.push(`search=${encodeURIComponent(this.doctorFinderSearchQuery)}`);
                }
                
                if (params.length > 0) {
                    url += '?' + params.join('&');
                }
                
                const response = await this.apiCall('GET', url);
                this.departmentDoctors = response.doctors;
            } catch (error) {
                console.error('Error loading doctors:', error);
            }
        },
        
        async searchDoctorsByName() {
            await this.loadDepartmentDoctors();
        },
        
        async viewDoctorProfile(doctor) {
            try {
                const response = await this.apiCall('GET', `/patient/doctors/${doctor.id}/profile`);
                this.selectedDoctor = response.doctor;
                this.showDoctorProfileModal = true;
            } catch (error) {
                console.error('Error loading doctor profile:', error);
                alert('Failed to load doctor profile');
            }
        },
        
        selectDoctorForBooking(doctor) {
            this.selectedDoctor = doctor;
            this.showDoctorsModal = false;
            this.showDoctorProfileModal = false;
            this.showBookingModal = true;
            this.bookingForm = {
                doctor_id: doctor.id,
                appointment_date: '',
                appointment_time: '',
                reason: ''
            };
            this.availableSlots = [];
            // Initialize calendar for current month
            this.initializeCalendar();
        },
        
        initializeCalendar() {
            const today = new Date();
            this.calendarYear = today.getFullYear();
            const monthIndex = today.getMonth();
            this.calendarMonth = today.toLocaleString('default', { month: 'long', year: 'numeric' });
            this.generateCalendarDates();
            this.loadMonthAvailability();
        },
        
        generateCalendarDates() {
            const year = this.calendarYear;
            const parts = this.calendarMonth.split(' ');
            const monthIndex = new Date(`${parts[0]} 1, ${parts[1]}`).getMonth();
            
            const firstDay = new Date(year, monthIndex, 1);
            const lastDay = new Date(year, monthIndex + 1, 0);
            const startDate = new Date(firstDay);
            startDate.setDate(startDate.getDate() - firstDay.getDay());
            
            this.calendarDates = [];
            let currentDate = new Date(startDate);
            
            while (currentDate <= lastDay || currentDate.getDay() !== 0) {
                // Use local date instead of UTC to avoid timezone issues
                const y = currentDate.getFullYear();
                const m = String(currentDate.getMonth() + 1).padStart(2, '0');
                const d = String(currentDate.getDate()).padStart(2, '0');
                const dateStr = `${y}-${m}-${d}`;
                
                const isCurrentMonth = currentDate.getMonth() === monthIndex;
                const isPast = currentDate < new Date(new Date().setHours(0, 0, 0, 0));
                
                this.calendarDates.push({
                    day: currentDate.getDate(),
                    dateStr: dateStr,
                    isCurrentMonth: isCurrentMonth,
                    isPast: isPast,
                    isDisabled: !isCurrentMonth || isPast,
                    isAvailable: false
                });
                
                currentDate.setDate(currentDate.getDate() + 1);
            }
        },
        
        async loadMonthAvailability() {
            try {
                if (!this.selectedDoctor?.id) return;
                
                // Create cache key for this doctor-month combination
                const cacheKey = `${this.selectedDoctor.id}_${this.calendarMonth}`;
                
                // Check if already cached
                if (this.availabilityCache[cacheKey]) {
                    // Use cached data
                    this.calendarDates = this.calendarDates.map(date => ({
                        ...date,
                        isAvailable: this.availabilityCache[cacheKey][date.dateStr] || false
                    }));
                    return;
                }
                
                // Get current month dates only (more efficient)
                const currentMonthDates = this.calendarDates
                    .filter(date => date.isCurrentMonth && !date.isPast)
                    .map(date => date.dateStr);
                
                if (currentMonthDates.length === 0) return;
                
                // Batch fetch availability for all dates in one request
                const resp = await this.apiCall('POST', `/patient/doctors/${this.selectedDoctor.id}/availability-batch`, {
                    dates: currentMonthDates
                });
                
                if (resp.availability) {
                    // Cache the result
                    this.availabilityCache[cacheKey] = resp.availability;
                    
                    // Update calendar dates with availability info
                    this.calendarDates = this.calendarDates.map(date => ({
                        ...date,
                        isAvailable: resp.availability[date.dateStr] || false
                    }));
                }
            } catch (e) {
                console.error('Error loading month availability:', e);
                // Fallback to marking all available on error
                this.calendarDates = this.calendarDates.map(date => ({
                    ...date,
                    isAvailable: !date.isDisabled
                }));
            }
        },
        
        async checkDateAvailability(dateStr) {
            // This method is kept for backward compatibility but should not be called
            // Use loadMonthAvailability() instead for batch operations
            try {
                const resp = await this.apiCall('GET', `/patient/doctors/${this.selectedDoctor.id}/slots?date=${encodeURIComponent(dateStr)}`);
                this.dateAvailability[dateStr] = (resp.slots && resp.slots.length > 0) ? true : false;
            } catch (e) {
                this.dateAvailability[dateStr] = false;
            }
        },
        
        prevMonth() {
            const [month, year] = this.calendarMonth.split(' ');
            const date = new Date(`${month} 1, ${year}`);
            date.setMonth(date.getMonth() - 1);
            this.calendarYear = date.getFullYear();
            this.calendarMonth = date.toLocaleString('default', { month: 'long', year: 'numeric' });
            this.generateCalendarDates();
            this.loadMonthAvailability();
        },
        
        nextMonth() {
            const [month, year] = this.calendarMonth.split(' ');
            const date = new Date(`${month} 1, ${year}`);
            date.setMonth(date.getMonth() + 1);
            this.calendarYear = date.getFullYear();
            this.calendarMonth = date.toLocaleString('default', { month: 'long', year: 'numeric' });
            this.generateCalendarDates();
            this.loadMonthAvailability();
        },
        
        selectAppointmentDate(dateStr) {
            this.bookingForm.appointment_date = dateStr;
            this.loadDoctorSlots();
        },
        
        getDateButtonClass(date) {
            if (!date.isCurrentMonth || date.isPast) {
                return ['btn', 'btn-sm', 'btn-light', 'text-muted'];
            }
            
            if (this.bookingForm.appointment_date === date.dateStr) {
                return ['btn', 'btn-sm', 'btn-primary'];
            }
            
            if (date.isAvailable) {
                return ['btn', 'btn-sm', 'btn-outline-success', 'available-date'];
            } else {
                return ['btn', 'btn-sm', 'btn-outline-danger', 'unavailable-date'];
            }
        },
        
        async loadDoctorSlots() {
            try {
                if (!this.bookingForm.appointment_date || !this.selectedDoctor?.id) {
                    this.availableSlots = [];
                    return;
                }
                const date = this.bookingForm.appointment_date;
                this.loadingSlotsDate = date;  // Show loading indicator
                const resp = await this.apiCall('GET', `/patient/doctors/${this.selectedDoctor.id}/slots?date=${encodeURIComponent(date)}`);
                this.availableSlots = resp.slots || [];
                // If selected time not in available slots, clear it
                if (!this.availableSlots.includes(this.bookingForm.appointment_time)) {
                    this.bookingForm.appointment_time = '';
                }
            } catch (e) {
                console.error('Error loading slots:', e);
                this.availableSlots = [];
            } finally {
                this.loadingSlotsDate = null;  // Hide loading indicator
            }
        },
        
        async bookAppointment() {
            try {
                if (!this.bookingForm.appointment_date || !this.bookingForm.appointment_time) {
                    this.showAlert('Please select a date and time slot', 'error');
                    return;
                }
                await this.apiCall('POST', '/patient/appointments', this.bookingForm);
                this.showAlert('Appointment booked successfully!', 'success');
                
                // Refresh available slots to remove the booked slot
                await this.loadDoctorSlots();
                
                // Clear booking form
                this.bookingForm = {
                    appointment_date: '',
                    appointment_time: '',
                    reason: ''
                };
                
                this.showBookingModal = false;
                await this.changePage('dashboard');
            } catch (error) {
                const errorMsg = error.response?.data?.error || 'Failed to book appointment';
                this.showAlert(errorMsg, 'error');
                
                // If slot was already booked by someone else, refresh slots list
                if (errorMsg.includes('not available') || errorMsg.includes('already have')) {
                    await this.loadDoctorSlots();
                }
            }
        },
        
        // Edit Appointment Calendar Methods
        initializeEditCalendar() {
            const today = new Date();
            this.editCalendarYear = today.getFullYear();
            const monthIndex = today.getMonth();
            this.editCalendarMonth = today.toLocaleString('default', { month: 'long', year: 'numeric' });
            this.generateEditCalendarDates();
            this.loadEditMonthAvailability();
        },
        
        generateEditCalendarDates() {
            const year = this.editCalendarYear;
            const monthIndex = new Date(`${this.editCalendarMonth.split(' ')[0]} 1`).getMonth();
            
            const firstDay = new Date(year, monthIndex, 1);
            const lastDay = new Date(year, monthIndex + 1, 0);
            const startDate = new Date(firstDay);
            startDate.setDate(startDate.getDate() - firstDay.getDay());
            
            this.editCalendarDates = [];
            let currentDate = new Date(startDate);
            
            while (currentDate <= lastDay || currentDate.getDay() !== 0) {
                // Use local date instead of UTC to avoid timezone issues
                const y = currentDate.getFullYear();
                const m = String(currentDate.getMonth() + 1).padStart(2, '0');
                const d = String(currentDate.getDate()).padStart(2, '0');
                const dateStr = `${y}-${m}-${d}`;
                
                const isCurrentMonth = currentDate.getMonth() === monthIndex;
                const isPast = currentDate < new Date(new Date().setHours(0, 0, 0, 0));
                
                this.editCalendarDates.push({
                    day: currentDate.getDate(),
                    dateStr: dateStr,
                    isCurrentMonth: isCurrentMonth,
                    isPast: isPast,
                    isDisabled: !isCurrentMonth || isPast,
                    isAvailable: false
                });
                
                currentDate.setDate(currentDate.getDate() + 1);
            }
        },
        
        async loadEditMonthAvailability() {
            try {
                if (!this.editingAppointment?.doctor_id) return;
                
                // Create cache key for this doctor-month combination
                const cacheKey = `${this.editingAppointment.doctor_id}_${this.editCalendarMonth}`;
                
                // Check if already cached
                if (this.editAvailabilityCache[cacheKey]) {
                    // Use cached data
                    this.editCalendarDates = this.editCalendarDates.map(date => ({
                        ...date,
                        isAvailable: this.editAvailabilityCache[cacheKey][date.dateStr] || false
                    }));
                    return;
                }
                
                // Get current month dates only (more efficient)
                const currentMonthDates = this.editCalendarDates
                    .filter(date => date.isCurrentMonth && !date.isPast)
                    .map(date => date.dateStr);
                
                if (currentMonthDates.length === 0) return;
                
                // Batch fetch availability for all dates in one request
                const resp = await this.apiCall('POST', `/patient/doctors/${this.editingAppointment.doctor_id}/availability-batch`, {
                    dates: currentMonthDates
                });
                
                if (resp.availability) {
                    // Cache the result
                    this.editAvailabilityCache[cacheKey] = resp.availability;
                    
                    // Update calendar dates with availability info
                    this.editCalendarDates = this.editCalendarDates.map(date => ({
                        ...date,
                        isAvailable: resp.availability[date.dateStr] || false
                    }));
                }
            } catch (e) {
                console.error('Error loading edit month availability:', e);
                // Fallback to marking all available on error
                this.editCalendarDates = this.editCalendarDates.map(date => ({
                    ...date,
                    isAvailable: !date.isDisabled
                }));
            }
        },
        
        async checkEditDateAvailability(dateStr) {
            // This method is kept for backward compatibility but should not be called
            // Use loadEditMonthAvailability() instead for batch operations
            try {
                const resp = await this.apiCall('GET', `/patient/doctors/${this.editingAppointment.doctor_id}/slots?date=${encodeURIComponent(dateStr)}`);
                this.editDateAvailability[dateStr] = (resp.slots && resp.slots.length > 0) ? true : false;
            } catch (e) {
                this.editDateAvailability[dateStr] = false;
            }
        },
        
        prevEditMonth() {
            const [month, year] = this.editCalendarMonth.split(' ');
            const date = new Date(`${month} 1, ${year}`);
            date.setMonth(date.getMonth() - 1);
            this.editCalendarYear = date.getFullYear();
            this.editCalendarMonth = date.toLocaleString('default', { month: 'long', year: 'numeric' });
            this.generateEditCalendarDates();
            this.loadEditMonthAvailability();
        },
        
        nextEditMonth() {
            const [month, year] = this.editCalendarMonth.split(' ');
            const date = new Date(`${month} 1, ${year}`);
            date.setMonth(date.getMonth() + 1);
            this.editCalendarYear = date.getFullYear();
            this.editCalendarMonth = date.toLocaleString('default', { month: 'long', year: 'numeric' });
            this.generateEditCalendarDates();
            this.loadEditMonthAvailability();
        },
        
        selectEditAppointmentDate(dateStr) {
            this.editAppointmentForm.appointment_date = dateStr;
            this.loadEditDoctorSlots();
        },
        
        getEditDateButtonClass(date) {
            if (!date.isCurrentMonth || date.isPast) {
                return ['btn', 'btn-sm', 'btn-light', 'text-muted'];
            }
            
            if (this.editAppointmentForm.appointment_date === date.dateStr) {
                return ['btn', 'btn-sm', 'btn-primary'];
            }
            
            if (date.isAvailable) {
                return ['btn', 'btn-sm', 'btn-outline-success', 'available-date'];
            } else {
                return ['btn', 'btn-sm', 'btn-outline-danger', 'unavailable-date'];
            }
        },
        
        async loadEditDoctorSlots() {
            try {
                if (!this.editAppointmentForm.appointment_date || !this.editingAppointment?.doctor_id) {
                    this.editAvailableSlots = [];
                    return;
                }
                const date = this.editAppointmentForm.appointment_date;
                this.loadingSlotsDate = date;  // Show loading indicator
                const resp = await this.apiCall('GET', `/patient/doctors/${this.editingAppointment.doctor_id}/slots?date=${encodeURIComponent(date)}`);
                this.editAvailableSlots = resp.slots || [];
                // If selected time not in available slots, clear it
                if (!this.editAvailableSlots.includes(this.editAppointmentForm.appointment_time)) {
                    this.editAppointmentForm.appointment_time = '';
                }
            } catch (e) {
                console.error('Error loading edit slots:', e);
                this.editAvailableSlots = [];
            } finally {
                this.loadingSlotsDate = null;  // Hide loading indicator
            }
        },
        
        editAppointment(appointment) {
            this.editingAppointment = appointment;
            this.editAppointmentForm = {
                appointment_date: appointment.appointment_date,
                appointment_time: appointment.appointment_time,
                reason: appointment.reason || ''
            };
            this.errorMessage = '';
            this.showEditAppointmentModal = true;
            // Initialize edit calendar
            this.initializeEditCalendar();
        },
        
        async updateAppointment() {
            try {
                this.isLoading = true;
                this.errorMessage = '';
                
                await this.apiCall('PUT', `/patient/appointments/${this.editingAppointment.id}`, this.editAppointmentForm);
                
                alert('Appointment updated successfully!');
                this.showEditAppointmentModal = false;
                this.editingAppointment = null;
                
                // Refresh appointments
                if (this.currentPage === 'appointments') {
                    await this.loadAppointments();
                } else {
                    await this.changePage('appointments');
                }
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to update appointment';
            } finally {
                this.isLoading = false;
            }
        },
        
        async cancelAppointmentById(appointmentId) {
            if (confirm('Are you sure you want to cancel this appointment?')) {
                try {
                    await this.apiCall('DELETE', `/patient/appointments/${appointmentId}`);
                    alert('Appointment cancelled successfully');
                    await this.changePage('dashboard');
                } catch (error) {
                    const errorMsg = error.response?.data?.error || 'Failed to cancel appointment';
                    alert(errorMsg);
                    console.error('Cancel appointment error:', error);
                }
            }
        },
        
        async sendAppointmentEmail(appointmentId) {
            try {
                const response = await this.apiCall('POST', `/admin/appointments/${appointmentId}/send-email`);
                alert('✉️ Email notification queued! It will be sent shortly to both the patient and doctor.');
                console.log('Email task queued:', response);
            } catch (error) {
                alert(error.response?.data?.error || 'Failed to send appointment email');
            }
        },
        
        completeAppointment(appointment) {
            this.currentAppointment = appointment;
            this.treatmentForm = {
                diagnosis: '',
                prescription: '',
                notes: '',
                next_visit_date: ''
            };
            this.showTreatmentModal = true;
        },
        
        openTreatmentModal(appointment) {
            this.completeAppointment(appointment);
        },
        
        async saveTreatment() {
            try {
                if (!this.treatmentForm.diagnosis || this.treatmentForm.diagnosis.trim() === '') {
                    alert('Diagnosis is required');
                    return;
                }
                await this.apiCall('POST', `/doctor/appointments/${this.currentAppointment.id}/complete`, this.treatmentForm);
                alert('Appointment completed successfully!');
                this.showTreatmentModal = false;
                await this.loadDoctorDashboard();
            } catch (error) {
                const errorMsg = error.response?.data?.error || 'Failed to complete appointment';
                alert(errorMsg);
                console.error('Save treatment error:', error);
            }
        },
        
        viewTreatmentDetails(treatment) {
            if (!treatment) {
                alert('No treatment details available');
                return;
            }
            const details = `
Treatment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Diagnosis: ${treatment.diagnosis}
Prescription: ${treatment.prescription || 'N/A'}
Notes: ${treatment.notes || 'N/A'}
Next Visit Date: ${treatment.next_visit_date ? new Date(treatment.next_visit_date).toLocaleDateString() : 'N/A'}
            `.trim();
            alert(details);
        },
        
        async exportTreatments() {
            try {
                // Start the export job
                const response = await this.apiCall('POST', '/patient/export');
                const jobId = response.job_id;
                
                this.showAlert('Export started! You will be notified when it is ready.', 'info');
                
                // Poll for completion
                const pollInterval = setInterval(async () => {
                    try {
                        const status = await this.apiCall('GET', `/patient/export/${jobId}`);
                        
                        if (status.status === 'Completed') {
                            clearInterval(pollInterval);
                            this.showAlert('Export completed! Downloading...', 'success');
                            
                            // Download file using fetch with authorization
                            try {
                                const response = await fetch(`http://localhost:5000/api/patient/export/${jobId}/download`, {
                                    headers: {
                                        'Authorization': `Bearer ${this.accessToken}`
                                    }
                                });
                                
                                if (response.ok) {
                                    const blob = await response.blob();
                                    const url = window.URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = `treatment_history_${jobId}.csv`;
                                    document.body.appendChild(a);
                                    a.click();
                                    window.URL.revokeObjectURL(url);
                                    document.body.removeChild(a);
                                } else {
                                    this.showAlert('Failed to download file', 'danger');
                                }
                            } catch (downloadErr) {
                                console.error('Download error:', downloadErr);
                                this.showAlert('Failed to download file', 'danger');
                            }
                            
                            // Refresh notifications
                            await this.checkNotifications();
                        } else if (status.status === 'Failed') {
                            clearInterval(pollInterval);
                            this.showAlert('Export failed. Please try again.', 'danger');
                        }
                    } catch (err) {
                        clearInterval(pollInterval);
                        console.error('Error checking export status:', err);
                    }
                }, 3000); // Check every 3 seconds
                
                // Stop polling after 2 minutes
                setTimeout(() => clearInterval(pollInterval), 120000);
            } catch (error) {
                console.error('Export error:', error);
                this.showAlert('Failed to start export', 'danger');
            }
        },
        
        async loadProfile() {
            try {
                // Load current user data into profile form
                this.profileForm = {
                    full_name: this.currentUser.full_name || '',
                    email: this.currentUser.email || '',
                    phone: this.currentUser.phone || '',
                    date_of_birth: '',
                    gender: '',
                    address: '',
                    blood_group: '',
                    emergency_contact: ''
                };
                
                // If patient, load patient-specific data
                if (this.currentUser.role === 'patient' && this.currentUser.patient_id) {
                    try {
                        const response = await this.apiCall('GET', '/patient/profile');
                        if (response.patient) {
                            this.profileForm.date_of_birth = response.patient.date_of_birth || '';
                            this.profileForm.gender = response.patient.gender || '';
                            this.profileForm.address = response.patient.address || '';
                            this.profileForm.blood_group = response.patient.blood_group || '';
                            this.profileForm.emergency_contact = response.patient.emergency_contact || '';
                        }
                        // Load patient treatment history
                        await this.loadPatientTreatmentHistory();
                    } catch (error) {
                        console.error('Error loading patient profile:', error);
                    }
                }
            } catch (error) {
                this.errorMessage = 'Failed to load profile';
            }
        },
        
        async updateProfile() {
            try {
                this.isLoading = true;
                this.errorMessage = '';
                this.successMessage = '';
                
                await this.apiCall('PUT', '/auth/profile', this.profileForm);
                
                // Reload user data
                const response = await this.apiCall('GET', '/auth/profile');
                this.currentUser = response.user;
                
                this.successMessage = 'Profile updated successfully!';
                this.isLoading = false;
                
                // Clear success message after 3 seconds
                setTimeout(() => {
                    this.successMessage = '';
                }, 3000);
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to update profile';
                this.isLoading = false;
            }
        },
        
        viewTreatment(appointment) {
            if (!appointment || !appointment.treatment) {
                alert('No treatment information available for this appointment');
                return;
            }
            
            const treatment = appointment.treatment;
            let treatmentDetails = `📋 Treatment Details\n\n`;
            treatmentDetails += `👨‍⚕️ Doctor: ${appointment.doctor_name}\n`;
            treatmentDetails += `📅 Date: ${appointment.appointment_date} at ${appointment.appointment_time}\n`;
            treatmentDetails += `====================================\n\n`;
            
            if (treatment.diagnosis) {
                treatmentDetails += `🔍 Diagnosis:\n${treatment.diagnosis}\n\n`;
            }
            
            if (treatment.prescription) {
                treatmentDetails += `💊 Prescription:\n${treatment.prescription}\n\n`;
            }
            
            if (treatment.notes) {
                treatmentDetails += `📝 Notes:\n${treatment.notes}\n\n`;
            }
            
            if (treatment.next_visit_date) {
                treatmentDetails += `📆 Next Visit: ${treatment.next_visit_date}`;
            }
            
            alert(treatmentDetails);
        },
        
        closeModal() {
            this.showAddDoctorModal = false;
            this.showBookingModal = false;
            this.showTreatmentModal = false;
            this.showEditAppointmentModal = false;
            this.showPatientHistoryModal = false;
            this.showEditTreatmentModal = false;
            this.editingDoctor = null;
            this.editingAppointment = null;
            this.doctorForm = {};
            this.editAppointmentForm = {};
            this.editTreatmentForm = {};
        },
        
        // Doctor: Load My Patients
        async loadMyPatients() {
            try {
                const response = await this.apiCall('GET', '/doctor/patients');
                this.myPatients = response.patients || [];
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to load patients';
                this.myPatients = [];
            }
        },
        
        // Doctor: View Patient History
        async viewPatientHistory(patient) {
            try {
                this.selectedPatient = patient;
                const response = await this.apiCall('GET', `/doctor/patients/${patient.id}/history`);
                this.patientHistory = response.history || [];
                this.showPatientHistoryModal = true;
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to load patient history';
            }
        },
        
        // Doctor: Open Edit Treatment Modal
        editTreatment(record) {
            this.editTreatmentForm = {
                treatment_id: record.treatment.id,
                diagnosis: record.treatment.diagnosis,
                prescription: record.treatment.prescription,
                notes: record.treatment.notes,
                next_visit_date: record.treatment.next_visit_date
            };
            this.showEditTreatmentModal = true;
        },
        
        // Doctor: Update Treatment Record
        async updateTreatmentRecord() {
            try {
                this.isLoading = true;
                this.errorMessage = '';
                
                await this.apiCall('PUT', `/doctor/treatments/${this.editTreatmentForm.treatment_id}`, {
                    diagnosis: this.editTreatmentForm.diagnosis,
                    prescription: this.editTreatmentForm.prescription,
                    notes: this.editTreatmentForm.notes,
                    next_visit_date: this.editTreatmentForm.next_visit_date
                });
                
                // Reload patient history
                const response = await this.apiCall('GET', `/doctor/patients/${this.selectedPatient.id}/history`);
                this.patientHistory = response.history || [];
                
                this.successMessage = 'Treatment updated successfully!';
                this.showEditTreatmentModal = false;
                this.isLoading = false;
                
                setTimeout(() => {
                    this.successMessage = '';
                }, 3000);
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to update treatment';
                this.isLoading = false;
            }
        },
        
        // Doctor: Cancel Appointment
        async cancelAppointmentDoctor(appointmentId) {
            if (!confirm('Are you sure you want to cancel this appointment?')) {
                return;
            }
            
            try {
                await this.apiCall('POST', `/doctor/appointments/${appointmentId}/cancel`);
                this.successMessage = 'Appointment cancelled successfully';
                
                // Reload dashboard if on dashboard page
                if (this.currentPage === 'dashboard') {
                    await this.loadDoctorDashboard();
                } else {
                    await this.loadAppointments();
                }
                
                setTimeout(() => {
                    this.successMessage = '';
                }, 3000);
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to cancel appointment';
            }
        },
        
        // Doctor: Load Availability
        async loadAvailability() {
            try {
                // Generate next 7 days
                this.availabilityDays = [];
                const today = new Date();
                const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                
                for (let i = 0; i < 7; i++) {
                    const date = new Date(today);
                    date.setDate(today.getDate() + i);
                    
                    const dateStr = date.toISOString().split('T')[0];
                    const dayName = dayNames[date.getDay()];
                    
                    this.availabilityDays.push({
                        date: dateStr,
                        dayName: dayName,
                        start_time: '09:00',
                        end_time: '17:00',
                        is_available: true
                    });
                }
                
                // Load existing availability
                const response = await this.apiCall('GET', '/doctor/availability');
                if (response.availability && response.availability.length > 0) {
                    response.availability.forEach(avail => {
                        const day = this.availabilityDays.find(d => d.date === avail.date);
                        if (day) {
                            day.start_time = avail.start_time;
                            day.end_time = avail.end_time;
                            day.is_available = avail.is_available;
                        }
                    });
                }
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to load availability';
            }
        },
        
        // Doctor: Save Availability
        async saveAvailability() {
            try {
                this.isLoading = true;
                this.errorMessage = '';
                this.successMessage = '';
                
                const availability = this.availabilityDays.map(day => ({
                    date: day.date,
                    start_time: day.start_time || '09:00',
                    end_time: day.end_time || '17:00',
                    is_available: day.is_available
                }));
                
                await this.apiCall('POST', '/doctor/availability/bulk', { availability });
                
                this.successMessage = 'Availability saved successfully!';
                this.isLoading = false;
                
                setTimeout(() => {
                    this.successMessage = '';
                }, 3000);
            } catch (error) {
                this.errorMessage = error.response?.data?.error || 'Failed to save availability';
                this.isLoading = false;
            }
        },
        
        // Doctor: Copy availability to all days
        copyToAll(index) {
            const sourceDay = this.availabilityDays[index];
            this.availabilityDays.forEach((day, i) => {
                if (i !== index) {
                    day.start_time = sourceDay.start_time;
                    day.end_time = sourceDay.end_time;
                    day.is_available = sourceDay.is_available;
                }
            });
        },
        
        getStatusBadgeClass(status) {
            const classes = {
                'Booked': 'bg-primary',
                'Completed': 'bg-success',
                'Cancelled': 'bg-danger'
            };
            return classes[status] || 'bg-secondary';
        }
    }
}).mount('#app');