import { configureStore } from '@reduxjs/toolkit'
import interactionReducer from './interactionSlice.js'

// Single store, single slice, no middleware/thunks - kept minimal per assignment spec
export const store = configureStore({
  reducer: {
    interaction: interactionReducer,
  },
})
