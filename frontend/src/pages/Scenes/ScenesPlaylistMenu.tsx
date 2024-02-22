import { useState, MouseEvent } from 'react'
import { Menu, MenuItem, ListItemIcon, Button } from '@mui/material'
import { MoreVert, Save } from '@mui/icons-material'
import Popover from '../../components/Popover/Popover'
import useStore from '../../store/useStore'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
import { download } from '../../utils/helpers'

const ScenesPlaylistMenu = () => {
  const scenePL = useStore((state) => state.scenePL)
  const setScenePL = useStore((state) => state.setScenePL)

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)

  const handleClose = () => {
    setAnchorEl(null)
  }
  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const fileChanged = async (e: any) => {
    const fileReader = new FileReader()
    fileReader.readAsText(e.target.files[0], 'UTF-8')
    fileReader.onload = (ev: any) => {
      if (ev.target.result && JSON.parse(ev.target.result).scenePL)
        setScenePL(JSON.parse(ev.target.result).scenePL)
    }
  }

  return (
    <>
      <Button variant="text" onClick={handleClick} sx={{ minWidth: '32px' }}>
        <MoreVert />
      </Button>
      <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
        <MenuItem
          onClick={() => {
            download({ scenePL }, 'ScenePlaylist.json', 'application/json')
            handleClose()
          }}
        >
          <ListItemIcon>
            <Save />
          </ListItemIcon>
        </MenuItem>
        <MenuItem>
          <input
            hidden
            accept="application/json"
            id="contained-button-file"
            type="file"
            onChange={(e) => fileChanged(e)}
          />
          <label
            htmlFor="contained-button-file"
            style={{ width: '100%', flexBasis: '49%' }}
          >
            <ListItemIcon>
              <BladeIcon name="mdi:folder-open" />
            </ListItemIcon>
          </label>
        </MenuItem>
        <Popover
          onConfirm={() => setScenePL([])}
          variant="outlined"
          color="inherit"
          style={{ marginRight: '0.5rem' }}
          type="menuItem"
        />
      </Menu>
    </>
  )
}

export default ScenesPlaylistMenu
