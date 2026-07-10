import { createSlice } from '@reduxjs/toolkit'

const initialState = {
  hcpName: '',
  interactionType: '',
  date: '',
  time: '',
  meetingLocation: '',
  attendees: '',
  topicsDiscussed: '',
  materialsShared: '',
  samplesDistributed: '',
  sentiment: '',
  outcomes: '',
  followUpActions: '',
  aiSuggestions: [],
  chatMessages: [],
  aiSummary: '',
  aiHospital: "",
  
  // Custom states
  selectedHcp: null,
  editingInteractionId: null,
  toast: null, // { message: string, type: 'success' | 'error' }
  aiMeetingLocation: '',

  // UI state
  loading: false,
  error: null,
}

const interactionSlice = createSlice({
  name: 'interaction',
  initialState,
  reducers: {
    updateField: (state, action) => {
      const { field, value } = action.payload
      state[field] = value
    },

    addChatMessage: (state, action) => {
      state.chatMessages.push(action.payload)
    },

    setAiSuggestions: (state, action) => {
      state.aiSuggestions = action.payload
    },

    setLoading: (state, action) => {
      state.loading = action.payload
    },

    setError: (state, action) => {
      state.error = action.payload
    },
    setAiSummary: (state, action) => {
      state.aiSummary = action.payload
    },
    setSelectedHcp: (state, action) => {
      state.selectedHcp = action.payload
      if (action.payload) {
        state.hcpName = action.payload.name
      }
    },
    setEditingInteractionId: (state, action) => {
      state.editingInteractionId = action.payload
    },
    loadInteractionToEdit: (state, action) => {
      const data = action.payload
      state.editingInteractionId = data.id
      state.selectedHcp = data.hcp || null
      state.hcpName = data.hcp ? data.hcp.name : ''
      state.interactionType = data.interaction_type || ''
      state.date = data.interaction_date || ''
      state.time = data.interaction_time || ''
      state.meetingLocation = data.meeting_location || ''
      state.aiMeetingLocation = data.meeting_location || ''
      state.attendees = data.attendees || ''
      state.topicsDiscussed = data.topics_discussed || ''
      state.sentiment = data.sentiment || ''
      state.outcomes = data.outcomes || ''
      state.followUpActions = data.follow_up_actions || ''
      state.materialsShared = data.materials ? data.materials.map(m => m.material_name).join(', ') : ''
      state.samplesDistributed = data.samples ? data.samples.map(s => `${s.quantity}x ${s.sample_name}`).join(', ') : ''
      state.aiSuggestions = data.ai_suggestions ? data.ai_suggestions.map(sug => sug.suggestion) : []
      state.aiSummary = data.ai_summary || ''
    },

    showToast: (state, action) => {
      state.toast = action.payload
    },
    clearToast: (state) => {
      state.toast = null
    },

    cancelEdit: (state) => {
      state.editingInteractionId = null
      state.interactionType = ''
      state.date = ''
      state.time = ''
      state.meetingLocation = ''
      state.aiMeetingLocation = ''
      state.attendees = ''
      state.topicsDiscussed = ''
      state.materialsShared = ''
      state.samplesDistributed = ''
      state.sentiment = ''
      state.outcomes = ''
      state.followUpActions = ''
      state.aiSuggestions = []
      state.aiSummary = ''
      state.aiHospital = "";
    },

    resetInteraction: () => initialState,
  },
})

export const {
  updateField,
  addChatMessage,
  setAiSuggestions,
  setAiSummary,
  setSelectedHcp,
  setEditingInteractionId,
  loadInteractionToEdit,
  showToast,
  clearToast,
  cancelEdit,
  resetInteraction
} = interactionSlice.actions

export default interactionSlice.reducer