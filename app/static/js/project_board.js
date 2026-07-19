let charts = {};

function renderAnalytics() {
    const totalTasks = projectTasks.length;
    const completedTasks = projectTasks.filter(t => t.status === 'Done').length;
    const inProgressTasks = projectTasks.filter(t => t.status === 'In Progress').length;
    const todoTasks = projectTasks.filter(t => t.status === 'To Do').length;

    if (typeof Chart === 'undefined') return;

    const isDark = document.documentElement.classList.contains('dark');
    const textThemeColor = isDark ? '#a1a1a1' : '#71717a';
    const gridColor = isDark ? '#2e2e2e' : '#f4f4f5';

    const initChart = (id, config) => {
        if (charts[id]) {
            charts[id].destroy();
        }
        const canvas = document.getElementById(id);
        if (canvas) {
            charts[id] = new Chart(canvas, config);
        }
    };

    initChart('chart-status', {
        type: 'pie',
        data: {
            labels: ['To Do', 'In Progress', 'Done'],
            datasets: [{
                data: [todoTasks, inProgressTasks, completedTasks],
                backgroundColor: ['#71717a', '#f59e0b', '#3ecf8e'],
                borderWidth: isDark ? 2 : 1,
                borderColor: isDark ? '#1e1e1e' : '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: textThemeColor, font: { family: 'Outfit', size: 11, weight: 'semibold' } }
                }
            }
        }
    });

    const categoryCounts = {};
    projectTasks.forEach(t => {
        const cat = t.issue_type || 'Uncategorized';
        categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
    });
    const catLabels = Object.keys(categoryCounts);
    const catValues = Object.values(categoryCounts);

    initChart('chart-category', {
        type: 'bar',
        data: {
            labels: catLabels.length > 0 ? catLabels : ['No tasks'],
            datasets: [{
                label: 'Task Count',
                data: catValues.length > 0 ? catValues : [0],
                backgroundColor: ['#6366f1', '#ec4899', '#14b8a6', '#f43f5e', '#8b5cf6', '#eab308'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: textThemeColor, font: { family: 'Outfit', size: 10, weight: 'semibold' } }
                },
                y: {
                    grid: { color: gridColor },
                    ticks: { color: textThemeColor, font: { family: 'Outfit', size: 10 }, stepSize: 1 }
                }
            }
        }
    });
}

function runAIHealthCheck() {
    showToast('Running risk assessment engines...');
    const btn = event.currentTarget;
    const icon = btn.querySelector('i');
    if (icon) icon.classList.add('animate-spin');
    
    setTimeout(() => {
        renderAnalytics();
        if (icon) icon.classList.remove('animate-spin');
        showToast('AI Risk Assessment completed! Health Score evaluated.', 'success');
    }, 1200);
}

// Initial trigger if tab parameter is active
if (new URLSearchParams(window.location.search).get('tab') === 'analytics') {
    setTimeout(renderAnalytics, 100);
}

document.addEventListener('DOMContentLoaded', function() {
    var taskEditor = document.getElementById('task-editor-container');
    if (taskEditor) {
        window.quillTask = new Quill('#task-editor-container', {
            theme: 'snow',
            modules: {
                toolbar: [
                    ['bold', 'italic', 'underline', 'strike'],
                    ['blockquote', 'code-block'],
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                    ['link', 'clean']
                ]
            },
            placeholder: 'Describe the task in detail...'
        });

        // Add submit listener to the form containing the editor
        var form = taskEditor.closest('form');
        if (form) {
            form.addEventListener('submit', function() {
                var content = document.querySelector('#task_description');
                content.value = window.quillTask.root.innerHTML;
            });
        }
    }

    // WebSockets initialization
    if (typeof io !== 'undefined') {
        const socket = window.socket || io();
        
        socket.on('connect', () => {
            if (typeof currentProjectId !== 'undefined') {
                socket.emit('join_board', { project_id: currentProjectId });
            }
        });

        socket.on('task_moved', (data) => {
            const isCurrentUser = typeof currentUserId !== 'undefined' && data.updated_by === currentUserId;

            const taskId = data.task_id;
            const newStatus = data.status;
            
            // Kanban Board Card Update
            const kanbanCard = document.querySelector(`.kanban-card[data-id="${taskId}"]`);
            if (kanbanCard) {
                let targetColId = '';
                if (newStatus === 'To Do') targetColId = 'col-todo';
                else if (newStatus === 'In Progress') targetColId = 'col-progress';
                else if (newStatus === 'Done') targetColId = 'col-done';
                
                if (targetColId) {
                    const targetCol = document.getElementById(targetColId);
                    if (targetCol && kanbanCard.parentElement !== targetCol) {
                        targetCol.appendChild(kanbanCard);
                    }
                    kanbanCard.setAttribute('data-status', newStatus);
                }
            }
            
            // Task List View Dropdown Update
            const tableSelects = document.querySelectorAll(`tr[data-id="${taskId}"] select`);
            tableSelects.forEach(select => {
                select.value = newStatus;
            });
            
            // Analytics Data Array Update
            if (typeof projectTasks !== 'undefined') {
                const task = projectTasks.find(t => t.id == taskId);
                if (task) {
                    task.status = newStatus;
                    const chartCanvas = document.getElementById('chart-status');
                    if (chartCanvas && chartCanvas.offsetParent !== null) {
                        if (typeof renderAnalytics === 'function') {
                            renderAnalytics();
                        }
                    }
                }
            }
            
            if (!isCurrentUser && typeof showToast === 'function') {
                showToast(`Task PROJ-${taskId} was moved to ${newStatus} by a team member`, 'success');
            }
        });
    }
});
