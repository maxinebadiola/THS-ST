let participantData = {
    //TODO: add watch timer
    name: '',
    age: 0,
    gender: '',
    startTime: null,
    endTime: null,
    videoInteractions: [],
    questionResponses: [],
    segmentInteractions: [],
    totalInteractions: 0
    //TODO: specific interactions
    //Pause
    //Play
    //Rewind
    //Forward
};

let currentQuestionIndex = 0;
let questionStartTime = null;
let studyStartTime = null;
let videoWatched = false;

//INSERT VIDEO SEGMENTS here
const videoSegments = [
    { name: "Introduction", start: 0, end: 30 },
    { name: "Weather Conditions", start: 30, end: 120 },
    { name: "Fire Behavior", start: 120, end: 240 },
    { name: "Emergency Response", start: 240, end: 360 },
    { name: "Community Impact", start: 360, end: 480 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 }
]
//survey
const questions = [
    {
        id: 1,
        question: "What were the primary weather conditions that contributed to the severity of Black Saturday?",
        type: "multiple-choice",
        options: [
            "High temperatures and strong winds",
            "Heavy rainfall and flooding",
            "Snow and freezing temperatures",
            "Mild conditions with light breeze"
        ],
        correctAnswer: 0
    },
    {
        id: 2,
        question: "How did the fire behavior differ from typical bushfires?",
        type: "multiple-choice",
        options: [
            "It moved slower than usual",
            "It created its own weather system",
            "It only burned at night",
            "It was easily contained"
        ],
        correctAnswer: 1
    }
];

//variables
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Set up event listeners
    document.getElementById('participant-form').addEventListener('submit', startStudy);
    document.getElementById('proceed-to-questions').addEventListener('click', showQuestions);
    document.getElementById('admin-toggle').addEventListener('click', toggleAdminPanel);
    document.getElementById('close-admin').addEventListener('click', closeAdminPanel);
    document.getElementById('download-data').addEventListener('click', downloadParticipantData);
    document.getElementById('export-all-data').addEventListener('click', exportAllData);
    document.getElementById('clear-data').addEventListener('click', clearAllData);
    document.getElementById('reset-study').addEventListener('click', resetStudy);

    //load stats
    updateAdminStats();
}

function startStudy(event) {
    event.preventDefault();
    
    // Collect participant information
    participantData.name = document.getElementById('participantName').value;
    participantData.age = parseInt(document.getElementById('participantAge').value);
    participantData.gender = document.getElementById('participantGender').value;
    participantData.startTime = new Date();
    studyStartTime = Date.now();
    
    // Hide participant setup and show video section
    document.getElementById('participant-setup').style.display = 'none';
    document.getElementById('video-section').style.display = 'block';
    document.getElementById('video-section').classList.add('fade-in');
    
    // Initialize video tracking
    initializeVideoTracking();
    createVideoSegments();
}

function initializeVideoTracking() {
    const video = document.getElementById('main-video');
    
    // Track video events
    const trackVideoEvent = (eventType, currentTime = null) => {
        const interaction = {
            type: eventType,
            timestamp: Date.now(),
            videoTime: currentTime || video.currentTime,
            relativeTime: Date.now() - studyStartTime
        };
        
        participantData.videoInteractions.push(interaction);
        participantData.totalInteractions++;
        updateInteractionCounter();
    };

    // Video event listeners
    video.addEventListener('play', () => trackVideoEvent('play'));
    video.addEventListener('pause', () => trackVideoEvent('pause'));
    video.addEventListener('seeked', () => trackVideoEvent('seek'));
    video.addEventListener('ratechange', () => trackVideoEvent('speed_change'));
    video.addEventListener('volumechange', () => trackVideoEvent('volume_change'));
    
    // Track video progress
    video.addEventListener('timeupdate', function() {
        updateVideoProgress();
        checkVideoCompletion();
    });
    
    video.addEventListener('loadedmetadata', function() {
        document.getElementById('duration').textContent = formatTime(video.duration);
    });
}

function createVideoSegments() {
    const segmentsContainer = document.getElementById('video-segments');
    segmentsContainer.innerHTML = '<h3>Video Segments</h3>';
    
    videoSegments.forEach((segment, index) => {
        const button = document.createElement('button');
        button.className = 'segment-button';
        button.textContent = `${segment.name} (${formatTime(segment.start)} - ${formatTime(segment.end)})`;
        button.addEventListener('click', () => jumpToSegment(segment, index));
        segmentsContainer.appendChild(button);
    });
}

function jumpToSegment(segment, index) {
    const video = document.getElementById('main-video');
    video.currentTime = segment.start;
    
    // Track segment interaction
    const segmentInteraction = {
        segmentIndex: index,
        segmentName: segment.name,
        timestamp: Date.now(),
        relativeTime: Date.now() - studyStartTime
    };
    
    participantData.segmentInteractions.push(segmentInteraction);
    participantData.totalInteractions++;
    updateInteractionCounter();
    
    // Update segment button states
    document.querySelectorAll('.segment-button').forEach((btn, i) => {
        btn.classList.toggle('active', i === index);
    });
}

function updateVideoProgress() {
    const video = document.getElementById('main-video');
    document.getElementById('current-time').textContent = formatTime(video.currentTime);
}

function checkVideoCompletion() {
    const video = document.getElementById('main-video');
    const watchThreshold = 0.8; // 80% of video watched
    
    if (video.currentTime / video.duration >= watchThreshold && !videoWatched) {
        videoWatched = true;
        document.getElementById('proceed-to-questions').style.display = 'block';
        document.getElementById('proceed-to-questions').classList.add('pulse');
    }
}

function updateInteractionCounter() {
    document.getElementById('interaction-count').textContent = `Interactions: ${participantData.totalInteractions}`;
}

function showQuestions() {
    document.getElementById('video-section').style.display = 'none';
    document.getElementById('questions-section').style.display = 'block';
    document.getElementById('questions-section').classList.add('fade-in');
    
    renderCurrentQuestion();
}

function renderCurrentQuestion() {
    if (currentQuestionIndex >= questions.length) {
        completeStudy();
        return;
    }
    
    const question = questions[currentQuestionIndex];
    const container = document.getElementById('questions-container');
    
    questionStartTime = Date.now();
    
    container.innerHTML = `
        <div class="question">
            <h3>Question ${currentQuestionIndex + 1} of ${questions.length}</h3>
            <p>${question.question}</p>
            <div class="question-options" id="question-options">
                ${renderQuestionOptions(question)}
            </div>
            <div class="question-timer">
                Time: <span id="question-timer">00:00</span>
            </div>
            <button id="next-question" class="btn btn-primary" style="margin-top: 20px; display: none;">
                ${currentQuestionIndex === questions.length - 1 ? 'Complete Study' : 'Next Question'}
            </button>
        </div>
    `;
    
    startQuestionTimer();
    setupQuestionInteraction(question);
}

function renderQuestionOptions(question) {
    if (question.type === 'multiple-choice') {
        return question.options.map((option, index) => `
            <div class="question-option" data-index="${index}">
                <input type="radio" name="q${question.id}" value="${index}" id="option${index}">
                <label for="option${index}">${option}</label>
            </div>
        `).join('');
    } else if (question.type === 'text') {
        return `
            <textarea id="text-answer" placeholder="Please provide your answer here..." rows="4"></textarea>
        `;
    }
}

function setupQuestionInteraction(question) {
    if (question.type === 'multiple-choice') {
        document.querySelectorAll('.question-option').forEach(option => {
            option.addEventListener('click', function() {
                const radio = this.querySelector('input[type="radio"]');
                radio.checked = true;
                
                document.querySelectorAll('.question-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                this.classList.add('selected');
                
                document.getElementById('next-question').style.display = 'block';
            });
        });
    } else if (question.type === 'text') {
        const textarea = document.getElementById('text-answer');
        textarea.addEventListener('input', function() {
            if (this.value.trim().length > 10) {
                document.getElementById('next-question').style.display = 'block';
            }
        });
    }
    
    document.getElementById('next-question').addEventListener('click', submitAnswer);
}

function startQuestionTimer() {
    const timerElement = document.getElementById('question-timer');
    const startTime = Date.now();
    
    const timer = setInterval(() => {
        const elapsed = Date.now() - startTime;
        timerElement.textContent = formatTime(elapsed / 1000);
    }, 1000);
    
    // Store timer to clear it later
    timerElement.timerId = timer;
}

function submitAnswer() {
    const question = questions[currentQuestionIndex];
    const completionTime = Date.now() - questionStartTime;
    
    let answer = null;
    let isCorrect = null;
    
    if (question.type === 'multiple-choice') {
        const selectedOption = document.querySelector('input[name="q' + question.id + '"]:checked');
        if (selectedOption) {
            answer = parseInt(selectedOption.value);
            isCorrect = question.correctAnswer !== null ? answer === question.correctAnswer : null;
        }
    } else if (question.type === 'text') {
        answer = document.getElementById('text-answer').value.trim();
        isCorrect = null; // Text answers require manual evaluation
    }
    
    // Store question response
    const response = {
        questionId: question.id,
        questionType: question.type,
        answer: answer,
        isCorrect: isCorrect,
        completionTime: completionTime,
        timestamp: Date.now()
    };
    
    participantData.questionResponses.push(response);
    
    // Clear timer
    const timerElement = document.getElementById('question-timer');
    if (timerElement.timerId) {
        clearInterval(timerElement.timerId);
    }
    
    // Move to next question
    currentQuestionIndex++;
    renderCurrentQuestion();
}

function completeStudy() {
    participantData.endTime = new Date();
    
    document.getElementById('questions-section').style.display = 'none';
    document.getElementById('completion-section').style.display = 'block';
    document.getElementById('completion-section').classList.add('fade-in');
    
    // Display completion statistics
    updateCompletionStats();
    
    // Save data to localStorage
    saveParticipantData();
}

function updateCompletionStats() {
    const totalTime = participantData.endTime - participantData.startTime;
    
    document.getElementById('total-time').textContent = formatTime(totalTime / 1000);
    document.getElementById('final-interactions').textContent = participantData.totalInteractions;
    document.getElementById('questions-answered').textContent = participantData.questionResponses.length;
}

function saveParticipantData() {
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    allData.push(participantData);
    localStorage.setItem('researchData', JSON.stringify(allData));
    updateAdminStats();
}

function downloadParticipantData() {
    const dataStr = JSON.stringify(participantData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `participant_${participantData.name}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
}

function resetStudy() {
    // Reset all variables
    participantData = {
        name: '',
        age: 0,
        gender: '',
        startTime: null,
        endTime: null,
        videoInteractions: [],
        questionResponses: [],
        segmentInteractions: [],
        totalInteractions: 0
    };
    
    currentQuestionIndex = 0;
    questionStartTime = null;
    studyStartTime = null;
    videoWatched = false;
    
    // Reset form
    document.getElementById('participant-form').reset();
    
    // Show participant setup
    document.getElementById('completion-section').style.display = 'none';
    document.getElementById('participant-setup').style.display = 'block';
    
    // Reset video
    const video = document.getElementById('main-video');
    video.currentTime = 0;
    document.getElementById('proceed-to-questions').style.display = 'none';
}

// Admin functions
function toggleAdminPanel() {
    document.getElementById('admin-panel').style.display = 'flex';
}

function closeAdminPanel() {
    document.getElementById('admin-panel').style.display = 'none';
}

function updateAdminStats() {
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    
    document.getElementById('admin-total-participants').textContent = allData.length;
    
    if (allData.length > 0) {
        const avgTime = allData.reduce((sum, participant) => {
            return sum + (new Date(participant.endTime) - new Date(participant.startTime));
        }, 0) / allData.length;
        
        const avgInteractions = allData.reduce((sum, participant) => {
            return sum + participant.totalInteractions;
        }, 0) / allData.length;
        
        document.getElementById('admin-avg-time').textContent = formatTime(avgTime / 1000);
        document.getElementById('admin-avg-interactions').textContent = Math.round(avgInteractions);
    }
}

function exportAllData() {
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    
    // Create CSV format for analysis
    let csvContent = "Participant Name,Age,Gender,Total Time (seconds),Video Interactions,Segment Interactions,Questions Answered,Accuracy Rate\n";
    
    allData.forEach(participant => {
        const totalTime = (new Date(participant.endTime) - new Date(participant.startTime)) / 1000;
        const correctAnswers = participant.questionResponses.filter(q => q.isCorrect === true).length;
        const totalAnswered = participant.questionResponses.filter(q => q.isCorrect !== null).length;
        const accuracyRate = totalAnswered > 0 ? (correctAnswers / totalAnswered * 100).toFixed(1) : 'N/A';
        
        csvContent += `${participant.name},${participant.age},${participant.gender},${totalTime},${participant.videoInteractions.length},${participant.segmentInteractions.length},${participant.questionResponses.length},${accuracyRate}%\n`;
    });
    
    // Also export detailed JSON data
    const jsonDataStr = JSON.stringify(allData, null, 2);
    
    // Download CSV
    const csvUri = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csvContent);
    const csvLink = document.createElement('a');
    csvLink.setAttribute('href', csvUri);
    csvLink.setAttribute('download', `research_data_summary_${new Date().toISOString().split('T')[0]}.csv`);
    csvLink.click();
    
    // Download JSON
    setTimeout(() => {
        const jsonUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(jsonDataStr);
        const jsonLink = document.createElement('a');
        jsonLink.setAttribute('href', jsonUri);
        jsonLink.setAttribute('download', `research_data_detailed_${new Date().toISOString().split('T')[0]}.json`);
        jsonLink.click();
    }, 1000);
}

function clearAllData() {
    if (confirm('Are you sure you want to clear all participant data? This action cannot be undone.')) {
        localStorage.removeItem('researchData');
        updateAdminStats();
        alert('All data has been cleared.');
    }
}

// Utility functions
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
}

// Prevent accidental page refresh during study
window.addEventListener('beforeunload', function (e) {
    if (studyStartTime && !participantData.endTime) {
        e.preventDefault();
        e.returnValue = '';
        return 'Are you sure you want to leave? Your progress will be lost.';
    }
});

// Auto-save functionality for data integrity
setInterval(() => {
    if (studyStartTime && participantData.name) {
        const tempData = {...participantData, tempSave: true, lastSaved: new Date()};
        localStorage.setItem('tempParticipantData', JSON.stringify(tempData));
    }
}, 30000); // Auto-save every 30 seconds
