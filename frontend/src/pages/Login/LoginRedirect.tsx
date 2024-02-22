import { useEffect, useState } from 'react'
import { useNavigate, useLocation, useParams } from 'react-router-dom'
import axios from 'axios'
import isElectron from 'is-electron'

const cloud = axios.create({
  baseURL: 'https://strapi.yeonv.com'
})
// const backendUrl = process.env.REACT_APP_BACKEND_URL;
const backendUrl = 'https://strapi.yeonv.com'

const LoginRedirect = () => {
  const [text, setText] = useState('Loading...')
  const location = useLocation()
  const params = useParams()
  const history = useNavigate()
  // console.log("OMG", params, props, location)
  useEffect(() => {
    // Successfully logged with the provider
    // Now logging with strapi by using the access_token (given by the provider) in props.location.search
    fetch(
      `${backendUrl}/auth/${params.providerName}/callback${location.search}`
    )
      .then((res) => {
        if (res.status !== 200) {
          throw new Error(`Couldn't login to Strapi. Status: ${res.status}`)
        }
        return res
      })
      .then((res) => res.json())
      .then(async (res) => {
        // Successfully logged with Strapi
        // Now saving the jwt to use it for future authenticated requests to Strapi
        localStorage.setItem('jwt', res.jwt)
        localStorage.setItem('username', res.user.username)
        const me = await cloud.get('users/me', {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('jwt')}`
          }
        })
        const user = await me.data
        // console.log(user)
        localStorage.setItem('ledfx-cloud-userid', user.id)
        localStorage.setItem('ledfx-cloud-role', user.role.type)
        setText(
          `You have been successfully logged in as ${localStorage.getItem(
            'username'
          )}. You will be redirected in a few seconds...`
        )
        setTimeout(() => {
          return isElectron() ? window.close() : history('/devices')
        }, 2000)
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.log(err)
        setText('An error occurred, please see the developer console.')
      })
  }, [history, location.search, params.providerName])

  return <p>{text}</p>
}

export default LoginRedirect
