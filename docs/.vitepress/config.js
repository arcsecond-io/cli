module.exports = {
  title: 'Arcsecond CLI',
  description: 'The command-line / Python module of Arcsecond.',
  base: '/cli/',
  cleanUrls: true,
  themeConfig: {
    nav: [
      { text: 'Arcsecond Docs', link: 'https://docs.arcsecond.io' }
    ],
    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: 'Install & Login', link: '/install' },
          { text: 'Data Upload', link: '/upload' }
        ]
      },
      {
        text: 'Self-Hosting',
        items: [
          { text: 'Live-Image Proxy', link: '/webcam' }
        ]
      },
      {
        text: 'Python API',
        items: [
          { text: 'API Basics', link: '/api-basics' },
          { text: 'Resources', link: '/resources' }
        ]
      }
    ]
  }
}
