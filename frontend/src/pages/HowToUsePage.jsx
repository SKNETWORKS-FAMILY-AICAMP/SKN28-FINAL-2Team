import Nav from '../components/Nav.jsx'
import How from '../components/How.jsx'
import Itinerary from '../components/Itinerary.jsx'
import Features from '../components/Features.jsx'
import Packages from '../components/Packages.jsx'
import FinalCTA from '../components/FinalCTA.jsx'
import useReveal from '../hooks/useReveal.js'

export default function HowToUsePage() {
  useReveal()

  return (
    <>
      <Nav />
      <How />
      <Itinerary />
      <Features />
      <Packages />
      <FinalCTA />
    </>
  )
}