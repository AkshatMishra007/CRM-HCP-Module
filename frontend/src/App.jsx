import { useSelector, useDispatch } from 'react-redux'
import { useEffect } from 'react'
import { clearToast } from './redux/interactionSlice'
import Header from './components/Header.jsx'
import InteractionForm from './components/InteractionForm.jsx'
import AIChat from './components/AIChat.jsx'

function App() {
  const toast = useSelector((state) => state.interaction.toast)
  const dispatch = useDispatch()

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        dispatch(clearToast())
      }, 4000)
      return () => clearTimeout(timer)
    }
  }, [toast, dispatch])

  return (
    <div className="min-h-screen bg-white relative">
      <Header />

      {/* Two-column layout: ~70% form / ~30% AI assistant.
          Stacks vertically on mobile, form first. */}
      <main className="mx-auto flex flex-col gap-6 p-6 lg:flex-row lg:items-start">
        <div className="w-full lg:w-[70%]">
          <InteractionForm />
        </div>
        <div className="w-full lg:w-[30%] lg:sticky lg:top-6">
          <div className="lg:h-[calc(100vh-3rem)]">
            <AIChat />
          </div>
        </div>
      </main>

      {/* Custom Toast Notification */}
      {toast && (
        <div className={`fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg border text-sm font-medium animate-bounce ${
          toast.type === 'error'
            ? 'bg-red-50 text-red-800 border-red-200'
            : 'bg-green-50 text-green-800 border-green-200'
        }`}>
          {toast.type === 'error' ? '⚠️' : '✅'}
          <span>{toast.message}</span>
          <button
            onClick={() => dispatch(clearToast())}
            className="ml-3 hover:opacity-70 text-xs font-bold"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  )
}

export default App
