// App shell placeholder. Owned by the frontend-shell agent.
import Thread from './components/thread/Thread'
import TrustReport from './pages/TrustReport'

export default function App() {
  void Thread
  return location.hash === '#/trust' ? <TrustReport /> : <div className="p-6">Verity</div>
}
