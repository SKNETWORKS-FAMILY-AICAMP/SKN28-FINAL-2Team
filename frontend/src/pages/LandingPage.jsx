import Nav from '../components/Nav.jsx'
import Hero from '../components/Hero.jsx'
import Footer from '../components/Footer.jsx'
import useReveal from '../hooks/useReveal.js'

export default function LandingPage() {
  useReveal()

  return (
    <div className="landing-page">
      <Nav />
      <main className="landing-main">
        <Hero />
      </main>
      <Footer />
    </div>
  )
}