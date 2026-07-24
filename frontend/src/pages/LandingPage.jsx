import Nav from '../components/Nav.jsx'
import Hero from '../components/Hero.jsx'
import How from '../components/How.jsx'
import Itinerary from '../components/Itinerary.jsx'
import Features from '../components/Features.jsx'
import Packages from '../components/Packages.jsx'
import Stats from '../components/Stats.jsx'
import FinalCTA from '../components/FinalCTA.jsx'
import Footer from '../components/Footer.jsx'
import useReveal from '../hooks/useReveal.js'

export default function LandingPage() {
  // Replicates the original IntersectionObserver-based scroll reveal
  useReveal()

  return (
    <>
      <Nav />
      <Hero />
      <How />
      <Itinerary />
      <Features />
      <Packages />
      <Stats />
      <FinalCTA />
      <Footer />
    </>
  )
}
