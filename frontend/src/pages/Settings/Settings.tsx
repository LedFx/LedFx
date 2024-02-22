import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Accordion, AccordionSummary, Typography } from '@mui/material'
import { SettingsAccordion, useStyles } from './SettingsComponents'
import useStore from '../../store/useStore'
import AudioCard from './AudioCard'
import WledCard from './WledCard'
import Webaudio from './Webaudio'
import ClientAudioCard from './ClientAudioCard'
import UICard from './UICard'
import GeneralCard from './GeneralCard'
import DashboardCard from './DashboardCard'
import AlphaFeatures from './AlphaFeatures'
import BetaFeatures from './BetaFeatures'
import ExpertFeatures from './ExpertFeatures'
import DevicesSection from './DevicesSection'
import SmartBar from '../../components/Dialogs/SmartBar'
import ScenesSection from './ScenesSection'
// import IntegrationsSection from './IntegrationsSection'

const Settings = () => {
  const classes = useStyles()
  const viewMode = useStore((state) => state.viewMode)
  const features = useStore((state) => state.features)
  const showFeatures = useStore((state) => state.showFeatures)
  const setSettingsExpanded = useStore((state) => state.ui.setSettingsExpanded)
  const loc = useLocation()

  useEffect(() => {
    if (loc.search.indexOf('ui') > -1) {
      setSettingsExpanded('panel2')
    }
  }, [loc])

  return (
    <div className={classes.card} style={{ marginBottom: '3rem' }}>
      <Accordion disabled sx={{ backgroundColor: 'transparent !important' }}>
        <AccordionSummary aria-controls="panel3a-content" id="panel3a-header">
          <Typography>Core Settings</Typography>
        </AccordionSummary>
      </Accordion>
      <SettingsAccordion title="General" accId="3" icon="Settings">
        <GeneralCard />
      </SettingsAccordion>
      <SettingsAccordion title="Audio" accId="1a" icon="Speaker">
        <>
          {features.webaudio && (
            <Webaudio
              style={{ position: 'absolute', right: '3.5rem', top: '0.3rem' }}
            />
          )}
          <ClientAudioCard />
          <AudioCard className={`${classes.audioCard} step-settings-one`} />
        </>
      </SettingsAccordion>

      <Accordion
        disabled
        sx={{ backgroundColor: 'transparent !important', pt: 3 }}
      >
        <AccordionSummary aria-controls="panel3a-content" id="panel3a-header">
          <Typography>Client Settings</Typography>
        </AccordionSummary>
      </Accordion>
      <SettingsAccordion title="Home" accId="1db" icon="Home">
        <DashboardCard />
      </SettingsAccordion>
      <SettingsAccordion
        title="Devices"
        accId="devicesSection"
        icon="mdi:led-strip-variant"
      >
        <DevicesSection />
      </SettingsAccordion>
      <SettingsAccordion title="Scenes" accId="scenesSection" icon="Image">
        <ScenesSection />
      </SettingsAccordion>
      {/* {viewMode !== 'user' && features.integrations && (
        <SettingsAccordion
          title="Integrations"
          accId="integrationsSection"
          icon="ElectricalServices"
        >
          <IntegrationsSection />
        </SettingsAccordion>
      )} */}
      <SettingsAccordion title="UI" accId="2a" icon="Widgets">
        <UICard />
      </SettingsAccordion>

      {viewMode !== 'user' && (
        <>
          <Accordion
            disabled
            sx={{ backgroundColor: 'transparent !important', pt: 3 }}
          >
            <AccordionSummary
              aria-controls="panel3a-content"
              id="panel3a-header"
            >
              <Typography>Client Features</Typography>
            </AccordionSummary>
          </Accordion>

          <SettingsAccordion title="Expert" accId="2y3" icon="Star">
            <ExpertFeatures />
          </SettingsAccordion>
          {features.beta && (
            <SettingsAccordion
              title="Beta"
              accId="2y2"
              icon="mdi:emoticon-devil"
            >
              <BetaFeatures />
            </SettingsAccordion>
          )}
          {features.alpha && showFeatures.alpha && (
            <SettingsAccordion
              title="Alpha"
              accId="2y1"
              icon="mdi:emoticon-devil-outline"
            >
              <AlphaFeatures />
            </SettingsAccordion>
          )}
        </>
      )}

      {features.wled && (
        <SettingsAccordion title="WLED" accId="4">
          <div>
            <WledCard className={`${classes.card} step-settings-five`} />
          </div>
        </SettingsAccordion>
      )}
      <div style={{ height: '1rem' }} />
      <SmartBar direct maxWidth={540} />
    </div>
  )
}

export default Settings
