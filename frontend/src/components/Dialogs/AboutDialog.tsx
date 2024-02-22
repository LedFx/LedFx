import { useState, useEffect } from 'react'
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link
} from '@mui/material'
import GitInfo from 'react-git-info/macro'
import useStore from '../../store/useStore'
import fversion from '../../../package.json'

export default function AboutDialog({ className, children, startIcon }: any) {
  const config = useStore((state) => state.config)
  const getInfo = useStore((state) => state.getInfo)
  const gitInfo = GitInfo()

  const [open, setOpen] = useState(false)
  const [bcommit, setBcommit] = useState('')
  const [bversion, setBversion] = useState('')

  const handleClickOpen = () => {
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
  }

  useEffect(() => {
    async function fetchData() {
      const info = await getInfo()
      if (info && info.git_build_commit) {
        setBcommit(info.git_build_commit)
        setBversion(info.version)
      }
    }

    if (open) {
      fetchData()
    }
  }, [open])

  return (
    <div>
      <Button
        size="small"
        startIcon={startIcon}
        className={className}
        onClick={handleClickOpen}
      >
        {children}
      </Button>
      <Dialog
        open={open}
        onClose={handleClose}
        aria-labelledby="about-dialog-title"
        aria-describedby="about-dialog-description"
        PaperProps={{
          style: { margin: '0 auto' }
        }}
      >
        <DialogTitle id="about-dialog-title">About LedFx</DialogTitle>
        <DialogContent>
          <div style={{ minWidth: 250 }}>
            <Card style={{ marginBottom: '1rem' }}>
              <CardHeader title="Backend" />
              <CardContent style={{ paddingTop: 0 }}>
                <div
                  style={{ display: 'flex', justifyContent: 'space-between' }}
                >
                  version: <span>{bversion}</span>{' '}
                </div>
                <div
                  style={{ display: 'flex', justifyContent: 'space-between' }}
                >
                  commit:{' '}
                  <Link
                    href={`https://github.com/LedFx/LedFx/commit/${bcommit}`}
                    target="_blank"
                  >
                    {bcommit.substring(0, 6)}
                  </Link>
                </div>
                <div
                  style={{ display: 'flex', justifyContent: 'space-between' }}
                >
                  config_version: <span>{config.configuration_version}</span>{' '}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader title="Frontend" />
              <CardContent style={{ paddingTop: 0 }}>
                <div
                  style={{ display: 'flex', justifyContent: 'space-between' }}
                >
                  version: <span>{fversion.version}</span>
                </div>
                <div
                  style={{ display: 'flex', justifyContent: 'space-between' }}
                >
                  commit:{' '}
                  <Link
                    href={`https://github.com/YeonV/LedFx-Frontend-v2/commit/${gitInfo.commit.hash}`}
                    target="_blank"
                  >
                    {gitInfo.commit.shortHash}
                  </Link>
                </div>
                <div
                  style={{ display: 'flex', justifyContent: 'space-between' }}
                >
                  config_version:{' '}
                  <span>{localStorage.getItem('ledfx-frontend')}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} autoFocus>
            OK
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
