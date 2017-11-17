"""
Problem 2: Logistic regression
You can choose to do one of the three following tasks:
Task 1: Improving the accuracy of our logistic regression on MNIST (objective 97 % accuracy on test set)

"""

import cv2
import os
import tensorflow as tf

from tensorflow.examples.tutorials.mnist import input_data
from tensorflow.contrib.data import TFRecordDataset



def load_mnist(path='./data'):
    mnist = input_data.read_data_sets(path, one_hot=True)
    return mnist


def simple_model(X, nb_class=10):
    flat_input = tf.keras.layers.Flatten()(X)

    fc1 = tf.keras.layers.Dense(100)(flat_input)
    fc1 = tf.keras.layers.Activation('relu')(fc1)

    fc2 = tf.keras.layers.Dense(200)(fc1)
    fc2 = tf.keras.layers.Activation('relu')(fc2)

    logits = tf.keras.layers.Dense(nb_class)(fc2)
    return logits


def perso_mnist_net_model_fn(features, labels, mode=tf.estimator.ModeKeys.TRAIN, params=None):

    """
    a model_fn for Estimator class

    This function will be called to create a new graph each time an estimator method is called
    """
    learning_rate = params['learning_rate']
    nb_class = 10
    tf.keras.backend.set_learning_phase(mode == tf.estimator.ModeKeys.TRAIN)

    X = features
    logits = simple_model(X, nb_class=nb_class)
    predictions = {'class': tf.argmax(logits, axis=1)}

    # Provide an estimator spec for `ModeKeys.PREDICT`.
    if mode == tf.estimator.ModeKeys.PREDICT:
        predictions['image'] = X
        return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)


    labels = tf.reshape(labels, [-1, nb_class])  # o: tf.squeeze
    Y = tf.cast(labels, tf.int32)
    with tf.name_scope('loss'):
        entropy = tf.nn.softmax_cross_entropy_with_logits(labels=tf.cast(labels, tf.float32), logits=logits)
        loss = tf.reduce_mean(entropy, name='loss') # computes the mean over all the examples in the batch


    gt_label = tf.argmax(Y, axis=1)
    accuracy = tf.contrib.metrics.accuracy(predictions['class'], gt_label)

    train_op = tf.train.AdamOptimizer(learning_rate).minimize(loss, global_step=tf.train.get_global_step())


    accuracy_metric = tf.contrib.metrics.streaming_accuracy(predictions['class'], gt_label)

    log_hook = tf.train.LoggingTensorHook(
        {
            'loss': loss,
            'accuracy': accuracy,
            'step': tf.train.get_global_step()
        }, every_n_iter=100)


    tf.summary.scalar('accuracy_' + mode, accuracy)

    return tf.estimator.EstimatorSpec(predictions=predictions, loss=loss, train_op=train_op, mode=mode,
                                      training_hooks=[log_hook], evaluation_hooks=[], eval_metric_ops={'acc_validation': accuracy_metric})


def get_input_fn_dataset(dataset_name = 'train', num_epoch=30, batch_size=256):
    # idea taken from https://stackoverflow.com/questions/45620449/initialization-of-tf-contrib-data-iterator-with-tf-estimator
    init_hook = IteratorInitHook()
    def _parse_function(example_proto):
      features = {"image": tf.FixedLenFeature([784], tf.float32),
                  "label": tf.FixedLenFeature([10], tf.float32)}
      parsed_features = tf.parse_example(example_proto, features)
      return parsed_features["image"], parsed_features["label"]

    def input_fn():
        dataset = TFRecordDataset('data/{}.tfrecords'.format(dataset_name), compression_type='GZIP')
        dataset = dataset.repeat(num_epoch)
        dataset = dataset.shuffle(10*batch_size)
        dataset = dataset.batch(batch_size)
        dataset = dataset.map(_parse_function)
        dataset = dataset.prefetch(10)

        iterator = dataset.make_initializable_iterator()
        init_hook.iterator_init_op = iterator.initializer
        #iterator = dataset.make_one_shot_iterator()
        return iterator.get_next()
    return input_fn, init_hook


class IteratorInitHook(tf.train.SessionRunHook):

    def after_create_session(self, session, coord):
        session.run(self.iterator_init_op)


def main():
    tf.app.flags.DEFINE_boolean("enable_estimator_log", False, """Enable logs of estimators""")
    if tf.app.flags.FLAGS.enable_estimator_log:
        tf.logging.set_verbosity(tf.logging.INFO)

    config= tf.estimator.RunConfig(save_summary_steps=10,
                                   save_checkpoints_steps=1000,
                                   keep_checkpoint_max=200,
                                   log_step_count_steps=1000)

    estimator = tf.estimator.Estimator(model_fn=perso_mnist_net_model_fn,
                                       model_dir='mnist_trained',
                                       params={'learning_rate': 0.01},
                                       config=config)

    input_train, input_train_init_hook = get_input_fn_dataset('train', batch_size=100, num_epoch=2)
    input_validation, input_validation_init_hook = get_input_fn_dataset('validation', batch_size=100, num_epoch=1)

    # start training and evaluation loop, training on 2 epoch then evaluate on validation dataset etc..
    for i in range(20):
        estimator.train(input_fn=input_train, hooks=[input_train_init_hook])
        res = estimator.evaluate(input_fn=input_validation, hooks=[input_validation_init_hook])
        print("validation is {}".format(res))


    input_test, input_test_init_hook = get_input_fn_dataset('test', batch_size=100, num_epoch=1)
    # print the accuracy on the test set (in our case we have the labels of the test case)
    test_set_res = estimator.evaluate(input_fn=input_test, hooks=[input_test_init_hook])
    print("Final res accuracy on test set is {}".format(test_set_res['acc_validation']))

    # we could just predict and save image in directory matching the class predicted without using the original labels
    debug_img_path = 'debug_img/{}'
    for num in range(10):
        os.makedirs(debug_img_path.format(num), exist_ok=True)

    generator = estimator.predict(input_fn=input_test, hooks=[input_test_init_hook])
    for num, val in enumerate(generator):
        cv2.imwrite(debug_img_path.format(val['class']) + '/_{}'.format(num) + '.png', 255 * val['image'].reshape(28, 28))


if __name__ == "__main__":
    main()
