import tensorflow as tf
import tfutil as t


tf.set_random_seed(777)


class DCGAN:

    def __init__(self, s, batch_size=64, height=32, width=32, channel=3,
                 sample_num=10 * 10, sample_size=10,
                 z_dim=128, gf_dim=64, df_dim=64, eps=1e-9):

        """
        # General Settings
        :param s: TF Session
        :param batch_size: training batch size, default 64
        :param height: input image height, default 32
        :param width: input image width, default 32
        :param channel: input image channel, default 3 (RGB)
        - in case of CIFAR, image size is 32x32x3(HWC).

        # Output Settings
        :param sample_num: the number of sample images, default 100
        :param sample_size: sample image size, default 10

        # Model Settings
        :param z_dim: z noise dimension, default 128
        :param gf_dim: the number of generator filters, default 64
        :param df_dim: the number of discriminator filters, default 64

        # Training Settings
        :param eps: epsilon, default 1e-12
        """

        self.s = s
        self.batch_size = batch_size
        self.height = height
        self.width = width
        self.channel = channel

        self.sample_size = sample_size
        self.sample_num = sample_num

        self.image_shape = [self.height, self.width, self.channel]

        self.z_dim = z_dim

        self.eps = eps

        self.gf_dim = gf_dim
        self.df_dim = df_dim

        # pre-defined
        self.d_loss = 0.
        self.g_loss = 0.

        self.g = None
        self.g_test = None

        self.d_op = None
        self.g_op = None

        self.merged = None
        self.writer = None
        self.saver = None

        # Placeholders
        self.x = tf.placeholder(tf.float32,
                                shape=[None, self.height, self.width, self.channel],
                                name='x-images')
        self.z = tf.placeholder(tf.float32, shape=[None, self.z_dim], name='z-noise')

        # Training Options
        self.beta1 = 0.5
        self.lr = 2e-4

        self.bulid_dcgan()  # build DCGAN model

    def discriminator(self, x, reuse=None):
        with tf.variable_scope('discriminator', reuse=reuse):
            x = t.conv2d(x, self.df_dim, name='d-conv-0')
            x = tf.nn.leaky_relu(x)

            x = t.conv2d(x, self.df_dim * 2, name='d-conv-1')
            x = t.batch_norm(x)
            x = tf.nn.leaky_relu(x)

            x = t.conv2d(x, self.df_dim * 4, name='d-conv-2')
            x = t.batch_norm(x)
            x = tf.nn.leaky_relu(x)

            x = t.conv2d(x, self.df_dim * 8, name='d-conv-3')
            x = t.batch_norm(x)
            x = tf.nn.leaky_relu(x)

            x = tf.layers.flatten(x)

            logits = t.dense(x, 1, name='d-fc-1')
            prob = tf.nn.sigmoid(logits)

            return prob, logits

    def generator(self, z, reuse=None, is_train=True):
        with tf.variable_scope('generator', reuse=reuse):
            x = t.dense(z, self.gf_dim * 8 * 4 * 4)

            x = tf.reshape(x, [-1, 4, 4, self.gf_dim * 8])
            x = t.batch_norm(x, is_train=is_train)
            x = tf.nn.leaky_relu(x)

            x = t.deconv2d(x, self.gf_dim * 4, name='g-deconv-1')
            x = t.batch_norm(x, is_train=is_train)
            x = tf.nn.leaky_relu(x)

            x = t.deconv2d(x,  self.gf_dim * 2, name='g-deconv-2')
            x = t.batch_norm(x, is_train=is_train)
            x = tf.nn.leaky_relu(x)

            logits = t.deconv2d(x, self.channel, name='g-deconv-3')
            prob = tf.nn.tanh(logits)

            return prob

    def bulid_dcgan(self):
        # Generator
        self.g = self.generator(self.z)
        self.g_test = self.generator(self.z, is_train=False)

        # Discriminator
        _, d_real = self.discriminator(self.x)
        _, d_fake = self.discriminator(self.g, reuse=True)

        # Losses
        """
        d_real_loss = -tf.reduce_mean(log(d_real))
        d_fake_loss = -tf.reduce_mean(log(1. - d_fake))
        self.d_loss = d_real_loss + d_fake_loss
        self.g_loss = -tf.reduce_mean(log(d_fake))
        """
        d_real_loss = t.sce_loss(d_real, tf.ones_like(d_real))
        d_fake_loss = t.sce_loss(d_fake, tf.zeros_like(d_fake))
        self.d_loss = d_real_loss + d_fake_loss
        self.g_loss = t.sce_loss(d_fake, tf.ones_like(d_fake))

        # Summary
        tf.summary.scalar("loss/d_real_loss", d_real_loss)
        tf.summary.scalar("loss/d_fake_loss", d_fake_loss)
        tf.summary.scalar("loss/d_loss", self.d_loss)
        tf.summary.scalar("loss/g_loss", self.g_loss)

        # Collect trainer values
        t_vars = tf.trainable_variables()
        d_params = [v for v in t_vars if v.name.startswith('d')]
        g_params = [v for v in t_vars if v.name.startswith('g')]

        # Optimizer
        self.d_op = tf.train.AdamOptimizer(learning_rate=self.lr,
                                           beta1=self.beta1).minimize(self.d_loss, var_list=d_params)
        self.g_op = tf.train.AdamOptimizer(learning_rate=self.lr,
                                           beta1=self.beta1).minimize(self.g_loss, var_list=g_params)

        # Merge summary
        self.merged = tf.summary.merge_all()

        # Model Saver
        self.saver = tf.train.Saver(max_to_keep=1)
        self.writer = tf.summary.FileWriter('./model/', self.s.graph)
