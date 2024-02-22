import { IconButton } from '@mui/material'
import GitHubIcon from '@mui/icons-material/GitHub'
import LanguageIcon from '@mui/icons-material/Language'
import ForumIcon from '@mui/icons-material/Forum'
import useStyles from './ButtonBar.styles'

const ButtonBar = () => {
  const classes = useStyles()

  return (
    <div className={classes.buttonBar}>
      <IconButton
        aria-label="Website"
        color="inherit"
        href="https://ledfx.app/"
        target="_blank"
        title="Website"
      >
        <LanguageIcon />
      </IconButton>
      <IconButton
        aria-label="Github"
        color="inherit"
        href="https://git.ledfx.app/"
        target="_blank"
        title="Github"
      >
        <GitHubIcon />
      </IconButton>
      <IconButton
        aria-label="Discord"
        color="inherit"
        href="https://discord.gg/wJ755dY"
        target="_blank"
        title="Discord"
      >
        <ForumIcon />
      </IconButton>
    </div>
  )
}

export default ButtonBar
