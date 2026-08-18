import AppHeader from '../components/AppHeader.jsx'
import Hero from '../components/Hero.jsx'
import Footer from '../components/Footer.jsx'
import useReveal from '../hooks/useReveal.js'

export default function LandingPage() {
  useReveal()

  return (
    <div className="landing-page">
      <AppHeader variant="main" />
      <main className="landing-main">
        <Hero />
      </main>
      <Footer />
    </div>
  )
}