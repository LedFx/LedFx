import axios from 'axios'

const cloud = axios.create({
  baseURL: 'https://strapi.yeonv.com'
})

const login = async (search: string) => {
  await fetch(`https://strapi.yeonv.com/auth/github/callback?${search}`)
    .then((res) => {
      if (res.status !== 200) {
        throw new Error(`Couldn't login to Strapi. Status: ${res.status}`)
      }
      return res
    })
    .then((res) => res.json())
    .then(async (res) => {
      localStorage.setItem('jwt', res.jwt)
      localStorage.setItem('username', res.user.username)
      const me = await cloud.get('users/me', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('jwt')}`
        }
      })
      const user = await me.data
      localStorage.setItem('ledfx-cloud-userid', user.id)
      localStorage.setItem('ledfx-cloud-role', user.role.type)
      // setTimeout(() => {
      //   return isElectron() ? window.close() : history('/devices')
      // }, 2000)
    })
    .catch((err) => {
      // eslint-disable-next-line no-console
      console.log(err)
    })
}

export default login
